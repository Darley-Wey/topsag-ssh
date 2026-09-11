#!/usr/bin/env python3
"""Open a TopSAG agent:// link in a new iTerm/Terminal window.

This is the browser URL-scheme helper. It does not log into the web console;
the page already generated a short-lived payload. CLI one-click SSH lives in
python/topsag_ssh.py and stays in the current terminal.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python"))

from crypto import LEGACY_FALLBACK_PASSWORD, parse_agent_scheme  # noqa: E402


def shlex_join(parts):
    import shlex

    return " ".join(shlex.quote(part) for part in parts)


def terminal_command(payload):
    alias = str(payload.get("alias") or "")
    session_id = str(payload.get("sessionId") or "")
    host = str(payload.get("serverIp") or "")
    port = str(payload.get("serverPort") or "2222")
    if not alias or not session_id or not host:
        raise SystemExit("agent:// payload is missing connection fields.")
    import base64

    user = base64.b64encode(f"{alias}@{session_id}".encode("utf-8")).decode("ascii")
    password = str(payload.get("serverPwd") or "")
    if not password or password == "@Encrypted":
        password = LEGACY_FALLBACK_PASSWORD
    protocol = str(payload.get("protocol") or "SSH").upper()
    auth_options = [
        "-o",
        "PreferredAuthentications=password,keyboard-interactive",
        "-o",
        "PubkeyAuthentication=no",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "ServerAliveInterval=15",
        "-o",
        "ServerAliveCountMax=3",
    ]
    if protocol in {"SFTP", "FTP"}:
        command = ["sftp"] + auth_options + [f"-oPort={port}", f"{user}@{host}"]
    else:
        command = ["ssh"] + auth_options + ["-p", port, f"{user}@{host}"]
    return command, password


def tcl_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\")
    for source, replacement in (
        ('"', '\\"'),
        ("$", "\\$"),
        ("[", "\\["),
        ("]", "\\]"),
        ("\r", "\\r"),
        ("\n", "\\n"),
    ):
        escaped = escaped.replace(source, replacement)
    return f'"{escaped}"'


def open_via_command_file(cmd_str: str, cleanup_paths=()):
    import shlex

    handle = tempfile.NamedTemporaryFile(
        "w", suffix=".command", delete=False, prefix="agentjump_"
    )
    cleanup = " ".join(shlex.quote(path) for path in (handle.name, *cleanup_paths))
    handle.write(
        "#!/bin/bash\n"
        f"trap 'rm -f -- {cleanup}' EXIT\n"
        "echo '=== AgentJump connection started ==='\n"
        f"{cmd_str}\n"
        "status=$?\n"
        "if [ $status -ne 0 ]; then\n"
        "  echo\n"
        '  echo "Connection failed (exit $status). Press Return to close."\n'
        "  read -r\n"
        "fi\n"
        "exit $status\n"
    )
    handle.close()
    os.chmod(handle.name, stat.S_IRWXU)
    if subprocess.run(["open", "-a", "iTerm", handle.name]).returncode != 0:
        subprocess.run(["open", handle.name], check=False)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: agent_jump.py 'agent://command&...&'", file=sys.stderr)
        return 64
    payload = parse_agent_scheme(sys.argv[1])
    command, password = terminal_command(payload)
    cleanup_paths = []
    if password:
        real_command = " ".join(tcl_quote(part) for part in command)
        expect_script = (
            "set timeout 60\n"
            f"spawn {real_command}\n"
            "expect {\n"
            f'    -re "(?i)password:" {{ send -- {tcl_quote(password)}\\r }}\n'
            '    timeout { puts stderr "Timed out waiting for the SSH password prompt."; exit 124 }\n'
            "    eof { catch wait result; exit [lindex $result 3] }\n"
            "}\n"
            "interact\n"
            "catch wait result\n"
            "exit [lindex $result 3]\n"
        )
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".exp", delete=False, prefix="agentjump_"
        )
        handle.write(expect_script)
        handle.close()
        cleanup_paths.append(handle.name)
        cmd_str = "expect " + __import__("shlex").quote(handle.name)
    else:
        cmd_str = shlex_join(command)
    open_via_command_file(cmd_str, cleanup_paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
