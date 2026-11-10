#!/usr/bin/env python3
"""Claude 세션 시작 시, 이 PC 설정이 허용한 MCP 중 로그인이 필요한 것만 인증한다.

허용 목록·건너뛰는 조건·시간 한도는 hooks/_shared/mcp_login.py 에 있다.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "_shared"))


def pending_servers(output):
    """`claude mcp list` 는 JSON 출력이 없어 사람이 읽는 줄에서 고른다. 문구가 바뀌면 빈 목록이 되어 아무것도 하지 않는다."""
    names = []
    for line in output.splitlines():
        if not re.search(r"\bneeds authentication\b", line, re.IGNORECASE):
            continue
        name, separator, _ = line.partition(": ")
        if separator and name.strip():
            names.append(name.strip())
    return names


def list_pending():
    try:
        result = subprocess.run(["claude", "mcp", "list"], capture_output=True, text=True, timeout=20, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return pending_servers(result.stdout)


if __name__ == "__main__":
    try:
        import mcp_login
    except Exception:
        sys.exit(0)
    mcp_login.main("claude", list_pending, ["claude", "mcp", "login"])
