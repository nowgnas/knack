#!/usr/bin/env python3
"""Codex 세션 시작 시, 이 PC 설정이 허용한 OAuth MCP 중 로그인이 필요한 것만 인증한다.

허용 목록·건너뛰는 조건·시간 한도는 hooks/_shared/mcp_login.py 에 있다.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "_shared"))
REMOTE = ("streamable_http", "sse")


def pending_servers(text):
    """`codex mcp list --json` 출력에서 켜져 있고 로그인이 필요한 원격 서버 이름. 형식이 다르면 None."""
    try:
        servers = json.loads(text)
    except ValueError:
        return None
    if not isinstance(servers, list):
        return None
    names = []
    for server in servers:
        if not isinstance(server, dict) or not isinstance(server.get("name"), str):
            continue
        transport = server.get("transport")
        kind = transport.get("type") if isinstance(transport, dict) else None
        if server.get("enabled") and server.get("auth_status") == "not_logged_in" and kind in REMOTE:
            names.append(server["name"])
    return names


def list_pending():
    try:
        listing = subprocess.run(["codex", "mcp", "list", "--json"], capture_output=True, text=True, timeout=15, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return pending_servers(listing.stdout)


if __name__ == "__main__":
    try:
        import mcp_login
    except Exception:
        sys.exit(0)
    mcp_login.main("codex", list_pending, ["codex", "mcp", "login"])
