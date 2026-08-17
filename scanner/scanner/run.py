"""Core scan execution: connects to Bedrock + RAPTOR MCP + Kali MCP and drives the agentic loop."""

import json
import logging
from dataclasses import dataclass, field
import re
from typing import Any
import os

import anthropic

from scanner.cost import TokenTracker
from scanner.events import ScanEventReporter
from scanner.mcp_client import call_tool, kali_mcp_session, raptor_mcp_session
from scanner.prompt import SYSTEM_PROMPT
from scanner.settings import ScanSettings

logger = logging.getLogger(__name__)

_CACHE_TTL = "5m"
_CACHE_CONTROL = {"type": "ephemeral", "ttl": _CACHE_TTL}
_REQUEST_TOKEN_SOFT_LIMIT = 18000
_RECENT_MESSAGE_COUNT = 6
_TOOL_RESULT_CHAR_LIMIT = 3000
_COMMAND_EVIDENCE_LINE_LIMIT = 20
_MAX_MEMORY_ITEMS = 12
_SUMMARY_MARKER = "Scan memory summary"
_SUMMARY_CONTINUE_MARKER = "Continue from the summarized scan state."


@dataclass
class ScanMemory:
    target_ip: str = ""
    target_host: str = ""
    open_ports: str = ""
    tested_by: str = ""
    security_details: str = ""
    checklist_template_count: int = 0
    matching_template_keys: list[str] = field(default_factory=list)
    existing_finding_titles: list[str] = field(default_factory=list)
    confirmed_findings: list[str] = field(default_factory=list)
    recent_actions: list[str] = field(default_factory=list)
    recent_observations: list[str] = field(default_factory=list)
    checklist_updates: list[str] = field(default_factory=list)
    recent_failures: list[str] = field(default_factory=list)
    compactions: int = 0
    last_compaction_tokens: int = 0

    def note_tool_result(self, tool_name: str, tool_input: dict, result: Any, summary: str, is_error: bool) -> None:
        if is_error:
            _append_capped(self.recent_failures, f"{tool_name}: {summary}", _MAX_MEMORY_ITEMS)
            return

        if tool_name == "get_pentest" and isinstance(result, dict):
            pentest = result.get("pentest", {}) if isinstance(result.get("pentest"), dict) else {}
            self.target_ip = str(pentest.get("ip_address") or self.target_ip).strip()
            self.target_host = str(pentest.get("dns_name") or self.target_host).strip()
            self.open_ports = str(pentest.get("open_ports") or self.open_ports).strip()
            self.tested_by = str(pentest.get("tested_by") or self.tested_by).strip()
            notes = str(pentest.get("notes") or "").strip()
            if notes:
                self.security_details = notes
            self.existing_finding_titles = _extract_existing_finding_titles(pentest.get("vulnerabilities"))
            return

        if tool_name == "update_pentest_ports":
            self.open_ports = str(tool_input.get("open_ports") or self.open_ports).strip()
            _append_capped(self.recent_observations, f"Open ports set to {self.open_ports}", _MAX_MEMORY_ITEMS)
            return

        if tool_name == "get_checklist_templates" and isinstance(result, dict):
            self.checklist_template_count = int(result.get("count") or 0)
            self.matching_template_keys = _matching_template_keys(result.get("templates"), self.open_ports)
            if self.matching_template_keys:
                _append_capped(
                    self.recent_observations,
                    f"Matching checklist templates: {', '.join(self.matching_template_keys)}",
                    _MAX_MEMORY_ITEMS,
                )
            return

        if tool_name == "update_checklist_item":
            template_key = str(tool_input.get("template_key") or "").strip()
            item_id = str(tool_input.get("item_id") or "").strip()
            status = str(tool_input.get("status") or "").strip()
            if template_key and item_id and status:
                _append_capped(self.checklist_updates, f"{template_key}:{item_id}={status}", _MAX_MEMORY_ITEMS)
            return

        if tool_name == "add_pentest_vulnerability":
            finding = _extract_finding_title(tool_input)
            if finding:
                _append_capped(self.confirmed_findings, finding, _MAX_MEMORY_ITEMS)
            return

        action = _tool_action_label(tool_name, tool_input)
        if action:
            _append_capped(self.recent_actions, action, _MAX_MEMORY_ITEMS)
        if summary:
            _append_capped(self.recent_observations, f"{tool_name}: {summary}", _MAX_MEMORY_ITEMS)

    def build_summary(self) -> str:
        lines = [f"{_SUMMARY_MARKER}:"]
        target = self.target_ip or "unknown"
        host = self.target_host or "unknown"
        ports = self.open_ports or "(not set)"
        lines.append(f"- Target: ip={target}, host={host}, open_ports={ports}")
        if self.tested_by:
            lines.append(f"- Assigned tester: {self.tested_by}")
        if self.security_details:
            lines.append(f"- Security details / credentials: {self.security_details[:400]}")
        if self.matching_template_keys:
            lines.append(f"- Matching checklist templates: {', '.join(self.matching_template_keys)}")
        elif self.checklist_template_count:
            lines.append(f"- Checklist templates loaded: {self.checklist_template_count}")
        if self.existing_finding_titles:
            lines.append(f"- Existing findings to avoid duplicating: {', '.join(self.existing_finding_titles[:6])}")
        if self.confirmed_findings:
            lines.append(f"- Findings added this run: {', '.join(self.confirmed_findings[-6:])}")
        if self.checklist_updates:
            lines.append(f"- Recent checklist updates: {', '.join(self.checklist_updates[-6:])}")
        if self.recent_actions:
            lines.append("- Recent tool actions:")
            lines.extend(f"  - {item}" for item in self.recent_actions[-6:])
        if self.recent_observations:
            lines.append("- Recent observations:")
            lines.extend(f"  - {item}" for item in self.recent_observations[-6:])
        if self.recent_failures:
            lines.append("- Recent tool failures:")
            lines.extend(f"  - {item}" for item in self.recent_failures[-4:])
        lines.append("- Keep using RAPTOR as the source of truth for stored findings and checklist state.")
        return "\n".join(lines)


async def run_scan(settings: ScanSettings) -> None:
    record_id = settings.record_id
    tracker = TokenTracker(
        cost_limit_usd=settings.cost_limit_usd,
        input_cost_per_1m=settings.input_cost_per_1m,
        output_cost_per_1m=settings.output_cost_per_1m,
    )
    proxy_url = settings.proxy_url.strip()
    if proxy_url and settings.proxy_username:
        from urllib.parse import quote
        user = quote(settings.proxy_username, safe="")
        pwd = quote(settings.proxy_password, safe="")
        scheme_end = proxy_url.find("://")
        if scheme_end != -1:
            proxy_url = f"{proxy_url[:scheme_end + 3]}{user}:{pwd}@{proxy_url[scheme_end + 3:]}"

    if proxy_url:
        # boto3/botocore (used for AWS credential signing) respects these env vars.
        # Must be set before AnthropicBedrock is constructed so the boto3 session
        # picks them up during credential resolution.
        os.environ["HTTPS_PROXY"] = proxy_url
        os.environ["HTTP_PROXY"] = proxy_url
        # Exclude internal Docker service hostnames from proxying — the proxy
        # can't resolve them and will return ERR_DNS_FAIL.
        os.environ["NO_PROXY"] = "mcp,app,kali,localhost,127.0.0.1"
        logger.info(f"[record {record_id}] Proxy configured: {settings.proxy_url.strip()}")
    else:
        os.environ.pop("HTTPS_PROXY", None)
        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("NO_PROXY", None)

    http_client = None
    if proxy_url:
        import httpx
        http_client = httpx.Client(
            proxy=proxy_url,
            mounts={"http://mcp": None, "http://app": None, "http://kali": None},
        )

    # AWS_BEARER_TOKEN_BEDROCK is read automatically by AnthropicBedrock.__init__
    # as api_key, which causes it to skip boto3/SigV4 entirely and just send
    # "Authorization: Bearer <token>". The http_client proxy covers that request.
    client = anthropic.AnthropicBedrock(
        aws_region=settings.aws_region,
        **({"http_client": http_client} if http_client else {}),
    )

    findings_count = 0
    async with raptor_mcp_session(settings.mcp_base_url, settings.mcp_server_token) as raptor_mcp:
        reporter = ScanEventReporter(record_id=record_id, raptor_mcp=raptor_mcp)
        try:
            async with kali_mcp_session(
                settings.kali_client_path,
                settings.kali_server_url,
                allow_destructive=settings.allow_destructive_tools,
            ) as kali_mcp:
                raptor_tools = await _get_mcp_tools_for_anthropic(raptor_mcp, source="raptor")
                kali_tools = await _get_mcp_tools_for_anthropic(
                    kali_mcp,
                    source="kali",
                    allow_destructive=settings.allow_destructive_tools,
                )
                all_tools = raptor_tools + kali_tools
                raptor_tool_names = {t["name"] for t in raptor_tools}
                kali_tool_names = {t["name"] for t in kali_tools}
                tool_registry = {
                    **{t["name"]: raptor_mcp for t in raptor_tools},
                    **{t["name"]: kali_mcp for t in kali_tools},
                }
                logger.info(
                    f"[record {record_id}] RAPTOR tools: {[t['name'] for t in raptor_tools]}  "
                    f"Kali tools: {[t['name'] for t in kali_tools]}"
                )
                await _set_scan_status(raptor_mcp, record_id, "running")
                await reporter.emit("status", {"scan_status": "running"})
                await _discover_ports(kali_mcp, raptor_mcp, settings, reporter)
                findings_count = await _agent_loop(
                    client, tool_registry, all_tools, settings, tracker, reporter,
                    raptor_tool_names, kali_tool_names,
                )
                await _set_scan_status(raptor_mcp, record_id, "completed")
                await reporter.emit("status", {"scan_status": "completed",
                                               "findings_count": findings_count,
                                               "input_tokens": tracker.input_tokens,
                                               "output_tokens": tracker.output_tokens,
                                               "cache_read_input_tokens": tracker.cache_read_input_tokens,
                                               "cache_creation_input_tokens": tracker.cache_creation_input_tokens,
                                               "cost_usd": round(tracker.cost_usd, 6)})
        except _CostLimitExceeded:
            logger.warning(f"[record {record_id}] Cost limit ${settings.cost_limit_usd} reached — marking failed")
            await _set_scan_status(raptor_mcp, record_id, "failed")
            await reporter.emit("status", {"scan_status": "failed", "reason": "cost_limit"})
            findings_count = 0
        except Exception as exc:
            reason = _summarize_exception(exc)
            logger.error(f"[record {record_id}] Scan error: {reason}", exc_info=True)
            await _set_scan_status(raptor_mcp, record_id, "failed")
            await reporter.emit("status", {"scan_status": "failed", "reason": reason[:200]})
            findings_count = 0
        finally:
            try:
                await call_tool(raptor_mcp, "notify_scan_complete", {
                    "record_id": record_id,
                    "findings_count": findings_count,
                    "input_tokens": tracker.input_tokens,
                    "output_tokens": tracker.output_tokens,
                    "cache_read_input_tokens": tracker.cache_read_input_tokens,
                    "cache_creation_input_tokens": tracker.cache_creation_input_tokens,
                    "cost_usd": tracker.cost_usd,
                })
            except Exception as exc:
                logger.error(f"[record {record_id}] Failed to send completion notification: {exc}")


async def _discover_ports(
    kali_mcp,
    raptor_mcp,
    settings: ScanSettings,
    reporter: ScanEventReporter,
) -> None:
    """Run nmap -p- TCP SYN discovery, save results via update_pentest_ports."""
    record_id = settings.record_id

    pentest_payload = await call_tool(raptor_mcp, "get_pentest", {"record_id": record_id})
    pentest = pentest_payload.get("pentest", {}) if isinstance(pentest_payload, dict) else {}
    existing_ports = str(pentest.get("open_ports") or "").strip()
    if existing_ports:
        logger.info(f"[record {record_id}] open_ports already set ({existing_ports!r}) — skipping discovery")
        return

    target_ip = str(pentest.get("ip_address") or "").strip()
    if not target_ip:
        logger.warning(f"[record {record_id}] No ip_address on pentest record — skipping port discovery")
        return

    logger.info(f"[record {record_id}] Starting port discovery on {target_ip}")
    await reporter.emit("status", {"scan_status": "running", "phase": "port_discovery"})

    try:
        result = await call_tool(kali_mcp, "execute_command", {
            "command": f"nmap -p- --open -T4 --min-rate 1000 -oG - {target_ip}",
            "timeout": 300,
        })
    except Exception as exc:
        logger.warning(f"[record {record_id}] Port discovery failed: {exc} — continuing without ports")
        return

    output = _extract_command_output(result)
    ports = _parse_nmap_open_ports(str(output or ""))
    ports_str = ",".join(str(p) for p in sorted(ports)) if ports else ""

    logger.info(f"[record {record_id}] Discovered ports: {ports_str or '(none)'}")
    if ports_str:
        try:
            await call_tool(raptor_mcp, "update_pentest_ports", {
                "record_id": record_id,
                "open_ports": ports_str,
            })
        except Exception as exc:
            logger.error(f"[record {record_id}] Failed to save open_ports: {exc}")
    else:
        logger.warning(f"[record {record_id}] No open ports found — scan will be marked failed by agent")


def _parse_nmap_open_ports(nmap_output: str) -> list[int]:
    import re
    ports = []
    for match in re.finditer(r"(\d+)/open", nmap_output):
        try:
            ports.append(int(match.group(1)))
        except ValueError:
            pass
    return ports


async def _agent_loop(
    client: anthropic.AnthropicBedrock,
    tool_registry: dict,
    tools: list,
    settings: ScanSettings,
    tracker: TokenTracker,
    reporter: ScanEventReporter,
    raptor_tool_names: set,
    kali_tool_names: set,
) -> int:
    record_id = settings.record_id
    findings_count = 0
    api_call_count = 0
    scan_memory = ScanMemory()
    initial_message = {
        "role": "user",
        "content": [{
            "type": "text",
            "text": (
                f"Begin security assessment for pentest record ID {record_id}.\n"
                f"Cost limit: ${settings.cost_limit_usd:.2f} USD. "
                f"Stop and call notify_scan_complete before this limit is reached.\n"
                f"Follow the workflow in your system instructions exactly. "
                f"Start with get_pentest({record_id})."
            ),
            "cache_control": dict(_CACHE_CONTROL),
        }],
    }
    messages = [
        {
            "role": initial_message["role"],
            "content": list(initial_message["content"]),
        }
    ]

    while True:
        if tracker.over_limit:
            raise _CostLimitExceeded()

        request_tools = _prepare_tools_for_request(tools)
        request_system = _build_system_blocks()
        request_messages = _prepare_messages_for_request(messages)
        preflight_tokens = _count_request_tokens(
            client=client,
            model=settings.bedrock_model_id,
            system=request_system,
            tools=request_tools,
            messages=request_messages,
        )
        if preflight_tokens is not None and (
            preflight_tokens > _REQUEST_TOKEN_SOFT_LIMIT
            or (api_call_count and api_call_count % 4 == 0 and len(messages) > 9)
        ):
            messages = _compact_messages(
                initial_message=initial_message,
                messages=messages,
                scan_memory=scan_memory,
                request_tokens=preflight_tokens,
            )
            scan_memory.compactions += 1
            scan_memory.last_compaction_tokens = preflight_tokens
            await reporter.emit("status", {
                "scan_status": "running",
                "phase": "context_compaction",
                "request_input_tokens": preflight_tokens,
                "compactions": scan_memory.compactions,
            })
            request_messages = _prepare_messages_for_request(messages)
            preflight_tokens = _count_request_tokens(
                client=client,
                model=settings.bedrock_model_id,
                system=request_system,
                tools=request_tools,
                messages=request_messages,
            )

        create_kwargs: dict = dict(
            model=settings.bedrock_model_id,
            max_tokens=16000,
            system=request_system,
            tools=request_tools,
            messages=request_messages,
        )
        if settings.thinking_budget_tokens > 0:
            create_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": settings.thinking_budget_tokens,
            }
        response = client.messages.create(**create_kwargs)

        api_call_count += 1
        cache_read_input_tokens = response.usage.cache_read_input_tokens or 0
        cache_creation_input_tokens = response.usage.cache_creation_input_tokens or 0
        tracker.add(
            response.usage.input_tokens,
            response.usage.output_tokens,
            cache_read_input_tokens=cache_read_input_tokens,
            cache_creation_input_tokens=cache_creation_input_tokens,
        )
        logger.info(
            f"[record {record_id}] tokens +{response.usage.input_tokens}in "
            f"+{response.usage.output_tokens}out  cache_read={cache_read_input_tokens} "
            f"cache_write={cache_creation_input_tokens}  cost ${tracker.cost_usd:.4f} "
            f"/ ${settings.cost_limit_usd:.2f}"
        )
        await reporter.emit("api_call", {
            "api_call_count": api_call_count,
            "request_input_tokens_preflight": preflight_tokens,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_read_input_tokens": cache_read_input_tokens,
            "cache_creation_input_tokens": cache_creation_input_tokens,
            "total_input_tokens": tracker.input_tokens,
            "total_output_tokens": tracker.output_tokens,
            "total_cache_read_input_tokens": tracker.cache_read_input_tokens,
            "total_cache_creation_input_tokens": tracker.cache_creation_input_tokens,
            "cost_usd": round(tracker.cost_usd, 6),
            "cost_limit_usd": settings.cost_limit_usd,
            "stop_reason": response.stop_reason,
        })

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason != "tool_use":
            logger.warning(f"[record {record_id}] Unexpected stop_reason: {response.stop_reason}")
            break

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            tool_name = block.name
            tool_input = block.input or {}
            mcp_source = "raptor" if tool_name in raptor_tool_names else ("kali" if tool_name in kali_tool_names else "unknown")
            logger.info(f"[record {record_id}] → {tool_name}({_safe_log(tool_input)})")
            await reporter.emit("tool_call", {
                "tool_name": tool_name,
                "mcp_source": mcp_source,
                "input_snippet": _safe_log(tool_input, max_len=300),
            })
            session = tool_registry.get(tool_name)
            if session is None:
                logger.warning(f"[record {record_id}] Unknown tool: {tool_name!r}")
                await reporter.emit("tool_result", {
                    "tool_name": tool_name,
                    "mcp_source": mcp_source,
                    "is_error": True,
                    "result_snippet": f"Unknown tool: {tool_name!r}",
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "is_error": True,
                    "content": f"Unknown tool: {tool_name!r}",
                })
                continue
            try:
                result = await call_tool(session, tool_name, tool_input)
                if tool_name == "add_pentest_vulnerability":
                    findings_count += 1
                    await reporter.emit("finding", {"findings_count": findings_count})
                result_str = _summarize_tool_result(tool_name, tool_input, result, scan_memory)
                scan_memory.note_tool_result(tool_name, tool_input, result, result_str, is_error=False)
                await reporter.emit("tool_result", {
                    "tool_name": tool_name,
                    "mcp_source": mcp_source,
                    "is_error": False,
                    "result_snippet": result_str[:300] if result_str else "",
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })
            except Exception as exc:
                logger.error(f"[record {record_id}] Tool {tool_name} failed: {exc}")
                error_summary = _truncate_text(str(exc), 500)
                scan_memory.note_tool_result(tool_name, tool_input, None, error_summary, is_error=True)
                await reporter.emit("tool_result", {
                    "tool_name": tool_name,
                    "mcp_source": mcp_source,
                    "is_error": True,
                    "result_snippet": error_summary[:300],
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "is_error": True,
                    "content": error_summary,
                })

        messages.append({"role": "user", "content": tool_results})

    return findings_count


_INTERNAL_TOOLS: set[str] = set()
_KALI_SAFE_TOOLS = {
    "server_health",
    "nmap_scan",
    "gobuster_scan",
    "dirb_scan",
    "nikto_scan",
    "nuclei_scan",
    "ffuf_scan",
    "wpscan_analyze",
    "enum4linux_scan",
}
_KALI_DESTRUCTIVE_TOOLS = {
    "execute_command",
    "sqlmap_scan",
    "metasploit_run",
    "hydra_attack",
    "john_crack",
}


async def _get_mcp_tools_for_anthropic(mcp, source: str, allow_destructive: bool = False) -> list:
    tools_list = await mcp.list_tools()
    result = []
    allowed = _KALI_SAFE_TOOLS | (_KALI_DESTRUCTIVE_TOOLS if allow_destructive else set())
    for tool in tools_list.tools:
        if tool.name in _INTERNAL_TOOLS:
            continue
        if source == "kali" and tool.name not in allowed:
            continue
        schema = tool.inputSchema if hasattr(tool, "inputSchema") else {}
        result.append({
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": schema,
        })
    return result


async def _set_scan_status(mcp, record_id: int, status: str) -> None:
    try:
        await call_tool(mcp, "set_scan_status", {"record_id": record_id, "scan_status": status})
    except Exception as exc:
        logger.error(f"[record {record_id}] Failed to set scan_status={status}: {exc}")


def _safe_log(obj: Any, max_len: int = 120) -> str:
    try:
        s = json.dumps(obj)
    except Exception:
        s = str(obj)
    return s[:max_len] + "…" if len(s) > max_len else s


def _build_system_blocks() -> list[dict]:
    return [{
        "type": "text",
        "text": SYSTEM_PROMPT,
        "cache_control": dict(_CACHE_CONTROL),
    }]


def _prepare_tools_for_request(tools: list[dict]) -> list[dict]:
    prepared = [dict(tool) for tool in tools]
    if prepared:
        prepared[-1]["cache_control"] = dict(_CACHE_CONTROL)
    return prepared


def _prepare_messages_for_request(messages: list[dict]) -> list[dict]:
    prepared: list[dict] = []
    for index, message in enumerate(messages):
        content = message.get("content")
        if isinstance(content, list):
            prepared_content = []
            for block_index, block in enumerate(content):
                if isinstance(block, dict):
                    block_copy = dict(block)
                    block_copy.pop("cache_control", None)
                    if index == 0 and block_index == 0 and block_copy.get("type") == "text":
                        block_copy["cache_control"] = dict(_CACHE_CONTROL)
                    prepared_content.append(block_copy)
                else:
                    prepared_content.append(block)
        else:
            prepared_content = content
        prepared.append({
            "role": message.get("role"),
            "content": prepared_content,
        })
    return prepared


def _count_request_tokens(
    client: anthropic.AnthropicBedrock,
    model: str,
    system: list[dict],
    tools: list[dict],
    messages: list[dict],
) -> int | None:
    try:
        response = client.messages.count_tokens(
            model=model,
            system=system,
            tools=tools,
            messages=messages,
        )
    except Exception as exc:
        logger.debug(f"Token preflight failed: {exc}")
        return None
    return response.input_tokens


def _compact_messages(initial_message: dict, messages: list[dict], scan_memory: ScanMemory, request_tokens: int) -> list[dict]:
    history = list(messages[1:])
    if len(history) >= 2 and _is_summary_assistant_message(history[0]) and _is_summary_user_message(history[1]):
        history = history[2:]

    recent_history = history[-_RECENT_MESSAGE_COUNT:] if len(history) > _RECENT_MESSAGE_COUNT else history
    summary_assistant = {
        "role": "assistant",
        "content": [{
            "type": "text",
            "text": scan_memory.build_summary(),
        }],
    }
    summary_user = {
        "role": "user",
        "content": [{
            "type": "text",
            "text": (
                f"{_SUMMARY_CONTINUE_MARKER} "
                f"The previous request was approximately {request_tokens} input tokens. "
                f"Use stored facts unless you need fresh evidence."
            ),
        }],
    }
    return [
        {
            "role": initial_message["role"],
            "content": list(initial_message["content"]),
        },
        summary_assistant,
        summary_user,
        *recent_history,
    ]


def _is_summary_assistant_message(message: dict) -> bool:
    if message.get("role") != "assistant":
        return False
    return _message_contains_text(message, _SUMMARY_MARKER)


def _is_summary_user_message(message: dict) -> bool:
    if message.get("role") != "user":
        return False
    return _message_contains_text(message, _SUMMARY_CONTINUE_MARKER)


def _message_contains_text(message: dict, needle: str) -> bool:
    content = message.get("content")
    if isinstance(content, str):
        return needle in content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and needle in str(block.get("text") or ""):
                return True
    return False


def _extract_command_output(result: Any) -> str:
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return ""
    for key in ("stdout", "output", "stderr"):
        value = result.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _iter_leaf_exceptions(exc: BaseException):
    if isinstance(exc, BaseExceptionGroup):
        for child in exc.exceptions:
            yield from _iter_leaf_exceptions(child)
        return
    yield exc


def _summarize_exception(exc: BaseException) -> str:
    for leaf in _iter_leaf_exceptions(exc):
        if isinstance(leaf, anthropic.RateLimitError):
            body = getattr(leaf, "body", None)
            if isinstance(body, dict):
                message = str(body.get("message") or "").strip()
                if message:
                    return f"Bedrock rate limit: {message}"
            message = str(leaf).strip()
            if message:
                return f"Bedrock rate limit: {message}"

    for leaf in _iter_leaf_exceptions(exc):
        message = str(leaf).strip()
        if message:
            return message

    message = str(exc).strip()
    return message or exc.__class__.__name__


def _summarize_tool_result(tool_name: str, tool_input: dict, result: Any, scan_memory: ScanMemory) -> str:
    if tool_name == "get_pentest":
        return _summarize_pentest_result(result)
    if tool_name == "get_checklist_templates":
        return _summarize_checklist_templates(result, scan_memory.open_ports)
    if tool_name == "execute_command":
        command = str(tool_input.get("command") or "").strip()
        return _summarize_execute_command_result(command, result)
    if tool_name == "update_checklist_item":
        return _summarize_scalar_result(result) or _tool_action_label(tool_name, tool_input)
    if tool_name == "add_pentest_vulnerability":
        return _summarize_add_vulnerability(tool_input, result)
    return _summarize_generic_result(result)


def _summarize_pentest_result(result: Any) -> str:
    if not isinstance(result, dict):
        return _truncate_text(str(result), _TOOL_RESULT_CHAR_LIMIT)
    pentest = result.get("pentest", {}) if isinstance(result.get("pentest"), dict) else {}
    fields = {
        "record_id": pentest.get("record_id") or pentest.get("id"),
        "pentest_id": pentest.get("id"),
        "target_ip": pentest.get("ip_address"),
        "target_host": pentest.get("dns_name"),
        "open_ports": pentest.get("open_ports"),
        "tested_by": pentest.get("tested_by"),
        "scan_status": pentest.get("scan_status"),
    }
    lines = [f"{key}={value}" for key, value in fields.items() if value not in (None, "", [])]
    notes = str(pentest.get("notes") or "").strip()
    if notes:
        lines.append(f"security_details={notes}")
    record_description = str(pentest.get("record_description") or "").strip()
    if record_description:
        lines.append(f"record_description={record_description}")
    titles = _extract_existing_finding_titles(pentest.get("vulnerabilities"))
    if titles:
        lines.append(f"existing_findings={', '.join(titles[:6])}")
    checklist_states = pentest.get("checklist_states")
    if checklist_states:
        lines.append(f"checklist_states_present={bool(str(checklist_states).strip())}")
    return _truncate_text("\n".join(lines), _TOOL_RESULT_CHAR_LIMIT)


def _summarize_checklist_templates(result: Any, open_ports: str) -> str:
    if not isinstance(result, dict):
        return _truncate_text(str(result), _TOOL_RESULT_CHAR_LIMIT)
    templates = result.get("templates") if isinstance(result.get("templates"), list) else []
    open_port_set = _parse_ports_csv(open_ports)
    lines = []
    matches = []
    for template in templates:
        auto_ports = _parse_ports_field(template.get("auto_ports"))
        if open_port_set and auto_ports and open_port_set.isdisjoint(auto_ports):
            continue
        matches.append(template)

    if not matches:
        return f"Loaded {int(result.get('count') or len(templates))} checklist templates. No templates match open_ports={open_ports or '(unset)'}."

    lines.append(f"Matching checklist templates for open_ports={open_ports or '(unset)'}:")
    for template in matches[:6]:
        key = str(template.get("key") or "").strip()
        name = str(template.get("name") or "").strip()
        auto_ports = sorted(_parse_ports_field(template.get("auto_ports")))
        lines.append(f"- {key or '(no-key)'}: {name} ports={auto_ports}")
        sections = _parse_json_field(template.get("sections"))
        if isinstance(sections, list):
            for section in sections[:4]:
                section_name = str(section.get("name") or "").strip()
                lines.append(f"  - Section: {section_name}")
                items = section.get("items") if isinstance(section.get("items"), list) else []
                for item in items[:8]:
                    item_id = str(item.get("id") or "").strip()
                    test_name = str(item.get("testName") or "").strip()
                    lines.append(f"    - {item_id}: {test_name}")
    return _truncate_text("\n".join(lines), max_chars=4000)


def _summarize_execute_command_result(command: str, result: Any) -> str:
    if not isinstance(result, dict):
        return _truncate_text(f"Command: {command}\n{result}", _TOOL_RESULT_CHAR_LIMIT)
    status = [
        f"command={command}",
        f"success={result.get('success')}",
        f"return_code={result.get('return_code')}",
        f"timed_out={result.get('timed_out')}",
    ]
    evidence = _extract_evidence_lines(_extract_command_output(result))
    stderr = result.get("stderr")
    if isinstance(stderr, str) and stderr.strip():
        evidence.extend(_extract_evidence_lines(stderr))
    if evidence:
        status.append("evidence:")
        status.extend(f"- {line}" for line in evidence[:_COMMAND_EVIDENCE_LINE_LIMIT])
    return _truncate_text("\n".join(status), _TOOL_RESULT_CHAR_LIMIT)


def _summarize_add_vulnerability(tool_input: dict, result: Any) -> str:
    finding = _extract_finding_title(tool_input) or "finding recorded"
    scalar = _summarize_scalar_result(result)
    return _truncate_text(f"{finding}\n{scalar}".strip(), _TOOL_RESULT_CHAR_LIMIT)


def _summarize_generic_result(result: Any) -> str:
    scalar = _summarize_scalar_result(result)
    if scalar:
        return scalar
    return _truncate_text(str(result), _TOOL_RESULT_CHAR_LIMIT)


def _summarize_scalar_result(result: Any) -> str:
    if isinstance(result, dict):
        lines = []
        for key, value in result.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                lines.append(f"{key}={value}")
            elif isinstance(value, list):
                lines.append(f"{key}=list[{len(value)}]")
            elif isinstance(value, dict):
                lines.append(f"{key}=object[{len(value)}]")
        return _truncate_text("\n".join(lines), _TOOL_RESULT_CHAR_LIMIT)
    if isinstance(result, str):
        return _truncate_text(result, _TOOL_RESULT_CHAR_LIMIT)
    return _truncate_text(str(result), _TOOL_RESULT_CHAR_LIMIT)


def _extract_existing_finding_titles(raw: Any) -> list[str]:
    findings = _parse_json_field(raw)
    if not isinstance(findings, list):
        return []
    titles = []
    for finding in findings[:12]:
        if not isinstance(finding, dict):
            continue
        description = str(finding.get("description") or "")
        title = _extract_markdown_title(description)
        if title:
            titles.append(title)
    return titles


def _extract_finding_title(tool_input: dict) -> str:
    description = str(tool_input.get("description") or "")
    title = _extract_markdown_title(description)
    if title:
        return title
    category_id = tool_input.get("category_id")
    return f"category_id={category_id}" if category_id else ""


def _extract_markdown_title(text: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def _append_capped(items: list[str], value: str, limit: int) -> None:
    value = value.strip()
    if not value:
        return
    items.append(value)
    if len(items) > limit:
        del items[: len(items) - limit]


def _tool_action_label(tool_name: str, tool_input: dict) -> str:
    if tool_name == "execute_command":
        command = str(tool_input.get("command") or "").strip()
        return f"command: {command[:120]}"
    if tool_name == "update_checklist_item":
        return (
            f"checklist {tool_input.get('template_key')}:{tool_input.get('item_id')} "
            f"-> {tool_input.get('status')}"
        )
    if tool_name == "add_pentest_vulnerability":
        return _extract_finding_title(tool_input)
    return f"{tool_name}({_safe_log(tool_input, max_len=120)})"


def _parse_json_field(raw: Any) -> Any:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw


def _parse_ports_field(raw: Any) -> set[int]:
    parsed = _parse_json_field(raw)
    ports: set[int] = set()
    if isinstance(parsed, list):
        for item in parsed:
            try:
                ports.add(int(item))
            except (TypeError, ValueError):
                continue
    return ports


def _parse_ports_csv(raw: str) -> set[int]:
    ports: set[int] = set()
    for item in str(raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            ports.add(int(item))
        except ValueError:
            continue
    return ports


def _matching_template_keys(templates: Any, open_ports: str) -> list[str]:
    if not isinstance(templates, list):
        return []
    open_port_set = _parse_ports_csv(open_ports)
    keys = []
    for template in templates:
        if not isinstance(template, dict):
            continue
        auto_ports = _parse_ports_field(template.get("auto_ports"))
        if open_port_set and auto_ports and open_port_set.isdisjoint(auto_ports):
            continue
        key = str(template.get("key") or "").strip()
        if key:
            keys.append(key)
    return keys[:_MAX_MEMORY_ITEMS]


def _extract_evidence_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    interesting = [
        line for line in lines
        if re.search(
            r"(open|closed|error|warning|http|https|ssl|title|server|found|forbidden|"
            r"redirect|timeout|cloudflare|vuln|critical|high|medium|low|cve-|nuclei|"
            r"inject|xss|sqli|traversal|exposure|disclosure|misconfiguration)",
            line, re.I,
        )
    ]
    selected = interesting[:_COMMAND_EVIDENCE_LINE_LIMIT]
    if len(selected) < min(len(lines), _COMMAND_EVIDENCE_LINE_LIMIT):
        for line in lines:
            if line in selected:
                continue
            selected.append(line)
            if len(selected) >= _COMMAND_EVIDENCE_LINE_LIMIT:
                break
    return selected


def _truncate_text(text: str, max_chars: int) -> str:
    text = text.strip()
    return text[:max_chars] + "…" if len(text) > max_chars else text


class _CostLimitExceeded(Exception):
    pass


__all__ = ["run_scan"]
