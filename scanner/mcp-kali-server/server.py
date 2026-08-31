#!/usr/bin/env python3

# This script connect the MCP AI agent to Kali Linux terminal and API Server.

# some of the code here was inspired from https://github.com/whit3rabbit0/project_astro , be sure to check them out

import argparse
import base64
import configparser
import json
import logging
import os
import re
import secrets
import shlex
import subprocess
import sys
import traceback
import threading
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
API_PORT = int(os.environ.get("API_PORT", 5000))
DEBUG_MODE = os.environ.get("DEBUG_MODE", "0").lower() in ("1", "true", "yes", "y")
COMMAND_TIMEOUT = 180  # 5 minutes default timeout

app = Flask(__name__)

KALI_INTERNAL_TOKEN = str(os.environ.get("KALI_INTERNAL_TOKEN") or "").strip()
DESTRUCTIVE_PATHS = {
    "/api/command",
    "/api/tools/sqlmap",
    "/api/tools/metasploit",
    "/api/tools/hydra",
    "/api/tools/john",
    "/api/tools/jwt",
}


@app.before_request
def require_kali_token():
    if request.path == "/health":
        return None
    if not KALI_INTERNAL_TOKEN:
        return jsonify({"error": "KALI_INTERNAL_TOKEN is not configured"}), 503
    provided = ""
    auth_header = request.headers.get("Authorization") or ""
    if auth_header.startswith("Bearer "):
        provided = auth_header[7:].strip()
    if not provided:
        provided = str(request.headers.get("X-Kali-Token") or "").strip()
    if (
        not provided
        or len(provided) != len(KALI_INTERNAL_TOKEN)
        or not secrets.compare_digest(provided, KALI_INTERNAL_TOKEN)
    ):
        return jsonify({"error": "Unauthorized"}), 401
    if request.path in DESTRUCTIVE_PATHS and request.headers.get("X-Kali-Destructive") != "1":
        return jsonify({"error": "Destructive tools are disabled"}), 403
    return None

class CommandExecutor:
    """Class to handle command execution with better timeout management"""

    def __init__(self, command, timeout: int = COMMAND_TIMEOUT, log_label: Optional[str] = None):
        self.command = command
        self.timeout = timeout
        self.log_label = log_label
        # Determine if we should use shell mode based on command type
        self.use_shell = isinstance(command, str)
        self.process = None
        self.stdout_data = ""
        self.stderr_data = ""
        self.stdout_thread = None
        self.stderr_thread = None
        self.return_code = None
        self.timed_out = False
    
    def _read_stdout(self):
        """Thread function to continuously read stdout"""
        for line in iter(self.process.stdout.readline, ''):
            self.stdout_data += line
    
    def _read_stderr(self):
        """Thread function to continuously read stderr"""
        for line in iter(self.process.stderr.readline, ''):
            self.stderr_data += line
    
    def execute(self) -> Dict[str, Any]:
        """Execute the command and handle timeout gracefully"""
        logger.info("Executing command: %s", self.log_label or self.command)
        
        try:
            self.process = subprocess.Popen(
                self.command,
                shell=self.use_shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )
            
            # Start threads to read output continuously
            self.stdout_thread = threading.Thread(target=self._read_stdout)
            self.stderr_thread = threading.Thread(target=self._read_stderr)
            self.stdout_thread.daemon = True
            self.stderr_thread.daemon = True
            self.stdout_thread.start()
            self.stderr_thread.start()
            
            # Wait for the process to complete or timeout
            try:
                self.return_code = self.process.wait(timeout=self.timeout)
                # Process completed, join the threads
                self.stdout_thread.join()
                self.stderr_thread.join()
            except subprocess.TimeoutExpired:
                # Process timed out but we might have partial results
                self.timed_out = True
                logger.warning(f"Command timed out after {self.timeout} seconds. Terminating process.")
                
                # Try to terminate gracefully first
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)  # Give it 5 seconds to terminate
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate
                    logger.warning("Process not responding to termination. Killing.")
                    self.process.kill()
                
                # Update final output
                self.return_code = -1
            
            # Always consider it a success if we have output, even with timeout
            success = True if self.timed_out and (self.stdout_data or self.stderr_data) else (self.return_code == 0)
            
            return {
                "stdout": self.stdout_data,
                "stderr": self.stderr_data,
                "return_code": self.return_code,
                "success": success,
                "timed_out": self.timed_out,
                "partial_results": self.timed_out and (self.stdout_data or self.stderr_data)
            }
        
        except Exception as e:
            logger.error(f"Error executing command: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "stdout": self.stdout_data,
                "stderr": f"Error executing command: {str(e)}\n{self.stderr_data}",
                "return_code": -1,
                "success": False,
                "timed_out": False,
                "partial_results": bool(self.stdout_data or self.stderr_data)
            }


def execute_command(command, log_label: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute a command and return the result.

    Args:
        command: The command to execute (list for safe mode, string for shell mode)
        log_label: Optional log text that must not contain secrets (JWTs, keys)

    Returns:
        A dictionary containing the stdout, stderr, and return code
    """
    executor = CommandExecutor(command, log_label=log_label)
    return executor.execute()


@app.route("/api/command", methods=["POST"])
def generic_command():
    """Execute any command provided in the request."""
    try:
        params = request.json
        command = params.get("command", "")
        
        if not command:
            logger.warning("Command endpoint called without command parameter")
            return jsonify({
                "error": "Command parameter is required"
            }), 400
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in command endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500


@app.route("/api/tools/nmap", methods=["POST"])
def nmap():
    """Execute nmap scan with the provided parameters."""
    try:
        params = request.json
        target = params.get("target", "")
        scan_type = params.get("scan_type", "-sCV")
        ports = params.get("ports", "")
        additional_args = params.get("additional_args", "-T4 -Pn")
        
        if not target:
            logger.warning("Nmap called without target parameter")
            return jsonify({
                "error": "Target parameter is required"
            }), 400        
        
        command = ["nmap"] + shlex.split(scan_type)

        if ports:
            command += ["-p", ports]

        if additional_args:
            command += shlex.split(additional_args)

        command.append(target)
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in nmap endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/gobuster", methods=["POST"])
def gobuster():
    """Execute gobuster with the provided parameters."""
    try:
        params = request.json
        url = params.get("url", "")
        mode = params.get("mode", "dir")
        wordlist = params.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        additional_args = params.get("additional_args", "")
        
        if not url:
            logger.warning("Gobuster called without URL parameter")
            return jsonify({
                "error": "URL parameter is required"
            }), 400
        
        # Validate mode
        if mode not in ["dir", "dns", "fuzz", "vhost"]:
            logger.warning(f"Invalid gobuster mode: {mode}")
            return jsonify({
                "error": f"Invalid mode: {mode}. Must be one of: dir, dns, fuzz, vhost"
            }), 400
        
        command = ["gobuster", mode, "-u", url, "-w", wordlist]

        if additional_args:
            command += shlex.split(additional_args)
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in gobuster endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/dirb", methods=["POST"])
def dirb():
    """Execute dirb with the provided parameters."""
    try:
        params = request.json
        url = params.get("url", "")
        wordlist = params.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        additional_args = params.get("additional_args", "")
        
        if not url:
            logger.warning("Dirb called without URL parameter")
            return jsonify({
                "error": "URL parameter is required"
            }), 400
        
        command = ["dirb", url, wordlist]

        if additional_args:
            command += shlex.split(additional_args)
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in dirb endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/nikto", methods=["POST"])
def nikto():
    """Execute nikto with the provided parameters."""
    try:
        params = request.json
        target = params.get("target", "")
        additional_args = params.get("additional_args", "")
        
        if not target:
            logger.warning("Nikto called without target parameter")
            return jsonify({
                "error": "Target parameter is required"
            }), 400
        
        command = ["nikto", "-h", target]

        if additional_args:
            command += shlex.split(additional_args)
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in nikto endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/sqlmap", methods=["POST"])
def sqlmap():
    """Execute sqlmap with the provided parameters."""
    try:
        params = request.json
        url = params.get("url", "")
        data = params.get("data", "")
        additional_args = params.get("additional_args", "")
        
        if not url:
            logger.warning("SQLMap called without URL parameter")
            return jsonify({
                "error": "URL parameter is required"
            }), 400
        
        command = ["sqlmap", "-u", url, "--batch"]

        if data:
            command += ["--data", data]

        if additional_args:
            command += shlex.split(additional_args)
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in sqlmap endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/metasploit", methods=["POST"])
def metasploit():
    """Execute metasploit module with the provided parameters."""
    try:
        params = request.json
        module = params.get("module", "")
        options = params.get("options", {})
        
        if not module:
            logger.warning("Metasploit called without module parameter")
            return jsonify({
                "error": "Module parameter is required"
            }), 400
        
        # Validate module name (allow only alphanumeric, slashes, underscores, hyphens)
        if not re.match(r'^[a-zA-Z0-9/_-]+$', module):
            return jsonify({"error": "Invalid module name"}), 400

        # Create an MSF resource script with validated options
        resource_content = f"use {module}\n"
        for key, value in options.items():
            # Validate option keys
            if not re.match(r'^[a-zA-Z0-9_]+$', str(key)):
                return jsonify({"error": f"Invalid option key: {key}"}), 400
            resource_content += f"set {key} {value}\n"
        resource_content += "exploit\n"

        # Save resource script to a temporary file
        resource_file = "/tmp/mks_msf_resource.rc"
        with open(resource_file, "w") as f:
            f.write(resource_content)

        command = ["msfconsole", "-q", "-r", resource_file]
        result = execute_command(command)
        
        # Clean up the temporary file
        try:
            os.remove(resource_file)
        except Exception as e:
            logger.warning(f"Error removing temporary resource file: {str(e)}")
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in metasploit endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/hydra", methods=["POST"])
def hydra():
    """Execute hydra with the provided parameters."""
    try:
        params = request.json
        target = params.get("target", "")
        service = params.get("service", "")
        username = params.get("username", "")
        username_file = params.get("username_file", "")
        password = params.get("password", "")
        password_file = params.get("password_file", "")
        additional_args = params.get("additional_args", "")
        
        if not target or not service:
            logger.warning("Hydra called without target or service parameter")
            return jsonify({
                "error": "Target and service parameters are required"
            }), 400
        
        if not (username or username_file) or not (password or password_file):
            logger.warning("Hydra called without username/password parameters")
            return jsonify({
                "error": "Username/username_file and password/password_file are required"
            }), 400
        
        command = ["hydra", "-t", "4"]

        if username:
            command += ["-l", username]
        elif username_file:
            command += ["-L", username_file]

        if password:
            command += ["-p", password]
        elif password_file:
            command += ["-P", password_file]

        command += [target, service]

        if additional_args:
            command += shlex.split(additional_args)
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in hydra endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/john", methods=["POST"])
def john():
    """Execute john with the provided parameters."""
    try:
        params = request.json
        hash_file = params.get("hash_file", "")
        wordlist = params.get("wordlist", "/usr/share/wordlists/rockyou.txt")
        format_type = params.get("format", "")
        additional_args = params.get("additional_args", "")
        
        if not hash_file:
            logger.warning("John called without hash_file parameter")
            return jsonify({
                "error": "Hash file parameter is required"
            }), 400
        
        command = ["john"]

        if format_type:
            command.append(f"--format={format_type}")

        if wordlist:
            command.append(f"--wordlist={wordlist}")

        if additional_args:
            command += shlex.split(additional_args)

        command.append(hash_file)
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in john endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*")
_CORRECT_KEY_LONG = re.compile(r"\[\+\] CORRECT key found:\s*(.+)", re.I)
_CORRECT_KEY_SHORT = re.compile(r"\[\+\] (.+) is the CORRECT key!", re.I)
JWT_TOOL_PY = "/opt/jwt_tool/jwt_tool.py"
JWT_WORDLIST = "/opt/jwt_tool/jwt-secrets.txt"
JWT_STEPS = (
    ("decode", []),
    ("none_alg", ["-X", "a"]),
    ("key_confusion", ["-X", "k"]),
    ("weak_secret", ["-C", "-d", JWT_WORDLIST]),
    ("claim_tamper", ["-I", "-pc", "role", "-pv", "admin"]),
)


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text or "")


def _redact_jwts(text: str) -> str:
    return _JWT_RE.sub("[jwt]", text or "")


def _jwt_tool_version() -> str:
    try:
        with open(JWT_TOOL_PY, encoding="utf-8", errors="ignore") as handle:
            blob = handle.read(8000)
        match = re.search(r'jwttoolvers\s*=\s*["\']([^"\']+)["\']', blob)
        if match:
            return match.group(1)
    except OSError:
        pass
    return "2.3.0"


def _rsa_module():
    try:
        from Cryptodome.PublicKey import RSA
        return RSA
    except ImportError:
        from Crypto.PublicKey import RSA
        return RSA


def _write_jwks(pub_path: str, jwks_path: str) -> None:
    try:
        RSA = _rsa_module()
    except ImportError:
        with open(jwks_path, "w", encoding="utf-8") as handle:
            json.dump({"keys": []}, handle)
        return
    key = RSA.importKey(open(pub_path, "rb").read())
    n_len = (key.n.bit_length() + 7) // 8
    e_len = (key.e.bit_length() + 7) // 8
    n = base64.urlsafe_b64encode(key.n.to_bytes(n_len, "big")).decode().rstrip("=")
    e = base64.urlsafe_b64encode(key.e.to_bytes(e_len, "big")).decode().rstrip("=")
    with open(jwks_path, "w", encoding="utf-8") as handle:
        json.dump({"keys": [{"kty": "RSA", "kid": "jwt_tool", "use": "sig", "n": n, "e": e}]}, handle)


def ensure_jwt_tool_config() -> str:
    """Write a jwt_tool ini that Python 3.14 can load. Comment-as-keys crash ConfigParser."""
    home = os.path.expanduser("~/.jwt_tool")
    os.makedirs(home, exist_ok=True)
    rsa_priv = os.path.join(home, "jwttool_custom_private_RSA.pem")
    rsa_pub = os.path.join(home, "jwttool_custom_public_RSA.pem")
    ec_priv = os.path.join(home, "jwttool_custom_private_EC.pem")
    ec_pub = os.path.join(home, "jwttool_custom_public_EC.pem")
    jwks_path = os.path.join(home, "jwttool_custom_jwks.json")
    conf_path = os.path.join(home, "jwtconf.ini")
    if not (os.path.isfile(rsa_priv) and os.path.isfile(rsa_pub)):
        subprocess.check_call(
            ["openssl", "genrsa", "-out", rsa_priv, "2048"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.check_call(
            ["openssl", "rsa", "-in", rsa_priv, "-pubout", "-out", rsa_pub],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    if not (os.path.isfile(ec_priv) and os.path.isfile(ec_pub)):
        subprocess.check_call(
            ["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", ec_priv],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.check_call(
            ["openssl", "ec", "-in", ec_priv, "-pubout", "-out", ec_pub],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    if not os.path.isfile(jwks_path):
        _write_jwks(rsa_pub, jwks_path)
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser["crypto"] = {
        "pubkey": rsa_pub,
        "privkey": rsa_priv,
        "ecpubkey": ec_pub,
        "ecprivkey": ec_priv,
        "jwks": jwks_path,
    }
    parser["customising"] = {
        "useragent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) jwt_tool",
        "jwks_kid": "jwt_tool",
    }
    parser["services"] = {
        "jwt_tool_version": _jwt_tool_version(),
        "proxy": "False",
        "redir": "False",
        "jwksloc": "",
        "jwksdynamic": "",
        "httplistener": "",
    }
    parser["input"] = {
        "wordlist": "jwt-common.txt",
        "commonHeaders": "common-headers.txt",
        "commonPayloads": "common-payloads.txt",
    }
    parser["argvals"] = {
        "sigType": "",
        "targetUrl": "",
        "rate": "999999999",
        "cookies": "",
        "key": "",
        "keyList": "",
        "keyFile": "",
        "headerLoc": "",
        "payloadclaim": "",
        "headerclaim": "",
        "payloadvalue": "",
        "headervalue": "",
        "canaryvalue": "",
        "header": "",
        "exploitType": "",
        "scanMode": "",
        "reqMode": "",
        "postData": "",
        "resCode": "",
        "resSize": "",
        "resContent": "",
    }
    with open(conf_path, "w", encoding="utf-8") as handle:
        parser.write(handle)
    return conf_path


def _jwt_step_ran(stdout: str, stderr: str) -> bool:
    blob = f"{stdout or ''}\n{stderr or ''}"
    if "Traceback (most recent call last)" in blob or "InvalidWriteError" in blob:
        return False
    if "Configuration file built" in blob:
        return False
    return any(
        marker in blob
        for marker in (
            "Original JWT",
            "Decoded Token Values",
            "CORRECT key",
            "not the correct key",
            "Exploit:",
        )
    )


def _jwt_hits_from_text(step: str, stdout: str) -> list:
    plain = _strip_ansi(stdout or "")
    hits = []
    match = _CORRECT_KEY_LONG.search(plain)
    if match:
        hits.append({"step": step, "kind": "weak_secret", "detail": match.group(1).strip()[:200]})
    match = _CORRECT_KEY_SHORT.search(plain)
    if match:
        hits.append({"step": step, "kind": "weak_secret", "detail": match.group(1).strip()[:200]})
    return hits


@app.route("/api/tools/jwt", methods=["POST"])
def jwt_attacks():
    """Fixed jwt_tool suite: decode, none alg, key confusion, weak secret, claim tamper."""
    try:
        params = request.json or {}
        token = str(params.get("token") or params.get("jwt") or "").strip()
        if not token:
            return jsonify({"error": "token is required", "success": False}), 400
        if not re.match(r"^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$", token):
            return jsonify({"error": "token is not a compact JWT", "success": False}), 400
        if not os.path.isfile(JWT_TOOL_PY):
            return jsonify({"error": "jwt_tool is not installed on this Kali image.", "success": False}), 503
        try:
            ensure_jwt_tool_config()
        except Exception as exc:
            logger.error("jwt_tool config setup failed: %s", exc)
            return jsonify({"error": "jwt_tool config could not be written.", "success": False}), 500
        combined = []
        hits = []
        for step_name, extra in JWT_STEPS:
            command = ["python3", JWT_TOOL_PY, token, "-np", *extra]
            display_cmd = " ".join(["python3", JWT_TOOL_PY, "[jwt]", "-np", *extra])
            result = execute_command(command, log_label=f"jwt_tool {step_name}")
            stdout_plain = _strip_ansi(result.get("stdout") or "")
            stderr_plain = _strip_ansi(result.get("stderr") or "")
            step_hits = _jwt_hits_from_text(step_name, stdout_plain)
            hits.extend(step_hits)
            ran = bool(step_hits) or _jwt_step_ran(stdout_plain, stderr_plain)
            combined.append(
                {
                    "step": step_name,
                    "command": display_cmd,
                    "stdout": _redact_jwts(stdout_plain)[:4000],
                    "stderr": _redact_jwts(stderr_plain)[:1500],
                    "return_code": result.get("return_code"),
                    "success": ran,
                }
            )
        ran_any = any(step.get("success") for step in combined)
        error = ""
        if not ran_any:
            error = next(
                (step.get("stderr") or "" for step in combined if step.get("stderr")),
                "jwt_tool failed on every step.",
            )
            error = error.strip().splitlines()[-1][:300] if error else "jwt_tool failed on every step."
        return jsonify(
            {
                "success": ran_any,
                "suite": combined,
                "hits": hits,
                "error": error,
                "host": params.get("host") or "",
                "path": params.get("path") or "",
            }
        )
    except Exception as e:
        logger.error("Error in jwt endpoint: %s", e)
        logger.error(traceback.format_exc())
        return jsonify({"error": f"Server error: {str(e)}", "success": False}), 500


@app.route("/api/tools/wpscan", methods=["POST"])
def wpscan():
    """Execute wpscan with the provided parameters."""
    try:
        params = request.json
        url = params.get("url", "")
        additional_args = params.get("additional_args", "")
        
        if not url:
            logger.warning("WPScan called without URL parameter")
            return jsonify({
                "error": "URL parameter is required"
            }), 400
        
        command = ["wpscan", "--url", url]

        if additional_args:
            command += shlex.split(additional_args)
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in wpscan endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/nuclei", methods=["POST"])
def nuclei():
    """Execute nuclei with the provided parameters."""
    try:
        params = request.json
        target = params.get("target", "")
        additional_args = params.get("additional_args", "")

        if not target:
            return jsonify({"error": "Target parameter is required"}), 400

        # Use -automatic-scan when no explicit template flags provided so nuclei
        # selects templates itself even if custom paths are absent.
        has_template_flag = additional_args and any(
            f in additional_args for f in ["-t ", "-tags ", "-template-id ", "-automatic-scan"]
        )
        command = ["nuclei", "-u", target, "-nc", "-silent"]
        if not has_template_flag:
            command.append("-automatic-scan")

        if additional_args:
            command += shlex.split(additional_args)

        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in nuclei endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/api/tools/ffuf", methods=["POST"])
def ffuf():
    """Execute ffuf with the provided parameters."""
    try:
        params = request.json
        url = params.get("url", "")
        wordlist = params.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        additional_args = params.get("additional_args", "")

        if not url:
            return jsonify({"error": "URL parameter is required"}), 400

        command = ["ffuf", "-u", url, "-w", wordlist, "-noninteractive", "-mc", "200,201,204,301,302,307,401,403,405,500"]

        if additional_args:
            command += shlex.split(additional_args)

        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in ffuf endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/api/tools/enum4linux", methods=["POST"])
def enum4linux():
    """Execute enum4linux with the provided parameters."""
    try:
        params = request.json
        target = params.get("target", "")
        additional_args = params.get("additional_args", "-a")
        
        if not target:
            logger.warning("Enum4linux called without target parameter")
            return jsonify({
                "error": "Target parameter is required"
            }), 400
        
        command = ["enum4linux"] + shlex.split(additional_args) + [target]
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in enum4linux endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500


# Health check endpoint
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    # Check if essential tools are installed
    essential_tools = ["nmap", "gobuster", "dirb", "nikto", "nuclei", "ffuf"]
    tools_status = {}
    
    for tool in essential_tools:
        try:
            result = execute_command(["which", tool])
            tools_status[tool] = result["success"]
        except:
            tools_status[tool] = False
    
    all_essential_tools_available = all(tools_status.values())
    
    return jsonify({
        "status": "healthy",
        "message": "Kali Linux Tools API Server is running",
        "tools_status": tools_status,
        "all_essential_tools_available": all_essential_tools_available
    })

@app.route("/mcp/capabilities", methods=["GET"])
def get_capabilities():
    # Return tool capabilities similar to our existing MCP server
    pass

@app.route("/mcp/tools/kali_tools/<tool_name>", methods=["POST"])
def execute_tool(tool_name):
    # Direct tool execution without going through the API server
    pass

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run the Kali Linux API Server")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--port", type=int, default=API_PORT, help=f"Port for the API server (default: {API_PORT})")
    parser.add_argument("--ip", type=str, default="127.0.0.1", help="IP address to bind the server to (default: 127.0.0.1 for localhost only)")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    # Set configuration from command line arguments
    if args.debug:
        DEBUG_MODE = True
        os.environ["DEBUG_MODE"] = "1"
        logger.setLevel(logging.DEBUG)
    
    if args.port != API_PORT:
        API_PORT = args.port
    
    logger.info(f"Starting Kali Linux Tools API Server on {args.ip}:{API_PORT}")
    app.run(host=args.ip, port=API_PORT, debug=DEBUG_MODE)
