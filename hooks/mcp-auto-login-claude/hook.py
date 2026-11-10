#!/usr/bin/env python3
"""지정 기기의 Claude MCP 중 인증이 필요한 서버만 순서대로 로그인한다."""
import fcntl
import getpass
import json
import os
import platform
import re
import subprocess
import tempfile


def notify(message):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": message}}, ensure_ascii=False))


def pending_servers(output):
    names = []
    for line in output.splitlines():
        if not re.search(r"\bneeds authentication\b", line, re.IGNORECASE):
            continue
        name, separator, _ = line.partition(": ")
        if separator and name.strip():
            names.append(name.strip())
    return names


def main():
    if platform.system() != "Darwin" or platform.node().split(".")[0] != "YPK7M177JY" or getpass.getuser() != "sangwolee":
        return
    try:
        result = subprocess.run(["claude", "mcp", "list"], capture_output=True, text=True, timeout=45, check=True)
        names = pending_servers(result.stdout)
    except (OSError, subprocess.SubprocessError):
        notify("Claude MCP 로그인 상태 확인에 실패했습니다. `claude mcp list`로 확인하세요.")
        return
    if not names:
        return
    lock_path = os.path.join(tempfile.gettempdir(), "knack-claude-mcp-login-" + str(os.getuid()) + ".lock")
    try:
        with open(lock_path, "a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                notify("다른 세션에서 Claude MCP 로그인이 진행 중입니다.")
                return
            failed = []
            for name in names:
                try:
                    result = subprocess.run(["claude", "mcp", "login", name], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=100)
                    if result.returncode:
                        failed.append(name)
                except (OSError, subprocess.TimeoutExpired):
                    failed.append(name)
            if failed:
                notify("Claude MCP 인증 실패 또는 시간 초과: " + ", ".join(failed) + ". 필요하면 `claude mcp login <이름>`을 실행하세요.")
    except OSError:
        notify("Claude MCP 로그인 잠금을 만들 수 없어 자동 인증을 건너뛰었습니다.")


if __name__ == "__main__":
    main()
