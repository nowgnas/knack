#!/usr/bin/env python3
"""지정 기기의 Codex OAuth MCP 미로그인 항목만 순서대로 인증한다."""
import fcntl
import getpass
import json
import os
import platform
import subprocess
import sys
import tempfile


def notify(message):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": message}}, ensure_ascii=False))


def main():
    if platform.system() != "Darwin" or platform.node().split(".")[0] != "YPK7M177JY" or getpass.getuser() != "sangwolee":
        return
    try:
        listing = subprocess.run(["codex", "mcp", "list", "--json"], capture_output=True, text=True, timeout=15, check=True)
        servers = json.loads(listing.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        notify("MCP 로그인 상태 확인에 실패했습니다. `codex mcp list`로 확인하세요.")
        return
    names = [server["name"] for server in servers if server.get("enabled") and server.get("auth_status") == "not_logged_in" and server.get("transport", {}).get("type") in ("streamable_http", "sse")]
    if not names:
        return
    lock_path = os.path.join(tempfile.gettempdir(), "knack-mcp-auto-login-" + str(os.getuid()) + ".lock")
    try:
        with open(lock_path, "a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                notify("다른 세션에서 MCP 로그인이 진행 중입니다.")
                return
            failed = []
            for name in names:
                try:
                    result = subprocess.run(["codex", "mcp", "login", name], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=100)
                    if result.returncode:
                        failed.append(name)
                except (OSError, subprocess.TimeoutExpired):
                    failed.append(name)
            if failed:
                notify("MCP 인증 실패 또는 시간 초과: " + ", ".join(failed) + ". 필요하면 `codex mcp login <이름>`을 실행하세요.")
    except OSError:
        notify("MCP 로그인 잠금을 만들 수 없어 자동 인증을 건너뛰었습니다.")


if __name__ == "__main__":
    main()
