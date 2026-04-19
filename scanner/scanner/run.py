"""Core scan execution: connects to Bedrock + RAPTOR MCP + Kali MCP and drives the agentic loop."""

import json
import logging
from typing import Any

import anthropic

from scanner.cost import TokenTracker
from scanner.mcp_client import call_tool, kali_mcp_session, raptor_mcp_session
from scanner.prompt import SYSTEM_PROMPT
from scanner.settings import ScanSettings

logger = logging.getLogger(__name__)


async def run_scan(settings: ScanSettings) -> None:
    record_id = settings.record_id
    tracker = TokenTracker(
        cost_limit_usd=settings.cost_limit_usd,
        input_cost_per_1m=settings.input_cost_per_1m,
        output_cost_per_1m=settings.output_cost_per_1m,
    )

    # AnthropicBedrock picks up AWS_BEARER_TOKEN_BEDROCK from the environment
    # automatically — no explicit credentials needed.
    client = anthropic.AnthropicBedrock(aws_region=settings.aws_region)

    findings_count = 0
    async with raptor_mcp_session(settings.mcp_base_url, settings.mcp_server_token) as raptor_mcp:
        try:
            async with kali_mcp_session(settings.kali_client_path, settings.kali_server_url) as kali_mcp:
                raptor_tools = await _get_mcp_tools_for_anthropic(raptor_mcp)
                kali_tools = await _get_mcp_tools_for_anthropic(kali_mcp)
                all_tools = raptor_tools + kali_tools
                tool_registry = {
                    **{t["name"]: raptor_mcp for t in raptor_tools},
                    **{t["name"]: kali_mcp for t in kali_tools},
                }
                logger.info(
                    f"[record {record_id}] RAPTOR tools: {[t['name'] for t in raptor_tools]}  "
                    f"Kali tools: {[t['name'] for t in kali_tools]}"
                )
                await _set_scan_status(raptor_mcp, record_id, "running")
                findings_count = await _agent_loop(client, tool_registry, all_tools, settings, tracker)
                await _set_scan_status(raptor_mcp, record_id, "completed")
        except _CostLimitExceeded:
            logger.warning(f"[record {record_id}] Cost limit ${settings.cost_limit_usd} reached — marking failed")
            await _set_scan_status(raptor_mcp, record_id, "failed")
            findings_count = 0
        except Exception as exc:
            logger.error(f"[record {record_id}] Scan error: {exc}", exc_info=True)
            await _set_scan_status(raptor_mcp, record_id, "failed")
            findings_count = 0
        finally:
            try:
                await call_tool(raptor_mcp, "notify_scan_complete", {
                    "record_id": record_id,
                    "findings_count": findings_count,
                    "input_tokens": tracker.input_tokens,
                    "output_tokens": tracker.output_tokens,
                    "cost_usd": tracker.cost_usd,
                })
            except Exception as exc:
                logger.error(f"[record {record_id}] Failed to send completion notification: {exc}")


async def _agent_loop(
    client: anthropic.AnthropicBedrock,
    tool_registry: dict,
    tools: list,
    settings: ScanSettings,
    tracker: TokenTracker,
) -> int:
    record_id = settings.record_id
    findings_count = 0
    messages = [
        {
            "role": "user",
            "content": (
                f"Begin security assessment for pentest record ID {record_id}.\n"
                f"Cost limit: ${settings.cost_limit_usd:.2f} USD. "
                f"Stop and call notify_scan_complete before this limit is reached.\n"
                f"Follow the workflow in your system instructions exactly. "
                f"Start with get_pentest({record_id})."
            ),
        }
    ]

    while True:
        if tracker.over_limit:
            raise _CostLimitExceeded()

        response = client.messages.create(
            model=settings.bedrock_model_id,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )

        tracker.add(response.usage.input_tokens, response.usage.output_tokens)
        logger.info(
            f"[record {record_id}] tokens +{response.usage.input_tokens}in "
            f"+{response.usage.output_tokens}out  cost ${tracker.cost_usd:.4f} "
            f"/ ${settings.cost_limit_usd:.2f}"
        )

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
            logger.info(f"[record {record_id}] → {tool_name}({_safe_log(tool_input)})")
            session = tool_registry.get(tool_name)
            if session is None:
                logger.warning(f"[record {record_id}] Unknown tool: {tool_name!r}")
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
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result) if not isinstance(result, str) else result,
                })
            except Exception as exc:
                logger.error(f"[record {record_id}] Tool {tool_name} failed: {exc}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "is_error": True,
                    "content": str(exc)[:500],
                })

        messages.append({"role": "user", "content": tool_results})

    return findings_count


async def _get_mcp_tools_for_anthropic(mcp) -> list:
    tools_list = await mcp.list_tools()
    result = []
    for tool in tools_list.tools:
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


class _CostLimitExceeded(Exception):
    pass


__all__ = ["run_scan"]
