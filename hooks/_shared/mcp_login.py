"""MCP 자동 로그인 훅(Claude·Codex)이 함께 쓰는 판단과 실행.

로그인은 브라우저를 띄우고 사람을 기다린다. 그래서 다음을 모두 만족할 때만 한다.
- 이 PC 의 설정 파일이 이 에이전트에 서버 이름을 허용했다 (파일이 없으면 아무것도 하지 않는다)
- 세션이 새로 시작됐다 (resume·clear·compact 가 아니다)
- 사람이 앞에 있는 세션이다 (CI·SSH·`claude -p`·`codex exec` 가 아니다)
판단할 수 없으면 로그인하지 않는다. 훅 오류로 세션을 멈추지 않는다(fail-open).
"""
import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CONFIG = Path(os.environ.get("KNACK_MCP_LOGIN_CONFIG") or
              Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "knack" / "mcp-auto-login.local.json")
NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.:@/-]*$")  # '-' 로 시작하면 CLI 옵션으로 읽힌다
BUDGET = 110        # 훅 전체가 세션 시작을 붙잡는 최대 시간(초). hook.json 의 timeout 보다 작아야 한다
LOGIN_TIMEOUT = 100
MAX_DEPTH = 6
HEADLESS = {"claude": re.compile(r"(^|\s)(-p|--print)(\s|$)"), "codex": re.compile(r"(^|\s)(exec|e|review)(\s|$)")}


def notify(message):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": message}},
                     ensure_ascii=False))


def allowed(agent):
    """설정 파일이 이 에이전트에 허용한 서버 이름. 파일이 없거나 형식이 다르면 빈 집합."""
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        names = data[agent]["servers"]
    except (OSError, ValueError, KeyError, TypeError):
        return set()
    if not isinstance(names, list):
        return set()
    return {n for n in names if isinstance(n, str) and NAME_RE.match(n)}


def hook_input():
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def ancestors():
    """부모 프로세스들의 명령줄. 읽지 못하면 None(판단 불가)."""
    out, pid = [], os.getppid()
    try:
        for _ in range(MAX_DEPTH):
            if pid <= 1:
                break
            p = subprocess.run(["ps", "-o", "ppid=,command=", "-p", str(pid)], capture_output=True, text=True, timeout=5)
            if p.returncode or not p.stdout.strip():
                break
            ppid, _, command = p.stdout.strip().partition(" ")
            out.append(command.strip())
            pid = int(ppid)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return out


def attended(agent, data, env=None, commands=ancestors):
    """사람이 로그인 창을 볼 수 있는 새 세션인가. 이유와 함께 돌려준다."""
    env = os.environ if env is None else env
    if data.get("source", "startup") != "startup":
        return False, "새 세션 시작이 아님"
    if env.get("CI") or env.get("SSH_CONNECTION") or env.get("SSH_TTY"):
        return False, "CI·SSH 세션"
    if agent == "claude" and env.get("CLAUDE_CODE_ENTRYPOINT", "").startswith("sdk"):
        return False, "SDK 실행"
    chain = commands()
    if chain is None:
        return False, "부모 프로세스를 읽지 못함"
    for command in chain:
        binary, _, args = command.partition(" ")
        if os.path.basename(binary) == agent and HEADLESS[agent].search(args):
            return False, "비대화 실행"
    return True, ""


def run(agent, pending, login_cmd, run_cmd=subprocess.run, clock=time.monotonic):
    """pending(로그인이 필요한 서버 이름) 중 허용된 것만 시간 한도 안에서 차례로 로그인한다."""
    allow = allowed(agent)
    names = [n for n in pending if n in allow]
    if not names:
        return
    deadline = clock() + BUDGET
    lock_path = os.path.join(tempfile.gettempdir(), f"knack-mcp-login-{agent}-{os.getuid()}.lock")
    try:
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except OSError:
        notify("MCP 로그인 잠금을 만들 수 없어 자동 인증을 건너뛰었습니다.")
        return
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            notify("다른 세션에서 MCP 로그인이 진행 중입니다.")
            return
        failed, skipped = [], []
        for name in names:
            left = deadline - clock()
            if left < 10:
                skipped.append(name)
                continue
            try:
                result = run_cmd([*login_cmd, name],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 timeout=min(LOGIN_TIMEOUT, left))
                if result.returncode:
                    failed.append(name)
            except (OSError, subprocess.SubprocessError):
                failed.append(name)
        parts = []
        if failed:
            parts.append("인증 실패 또는 시간 초과: " + ", ".join(failed))
        if skipped:
            parts.append("시간 한도로 건너뜀: " + ", ".join(skipped))
        if parts:
            notify(f"MCP 자동 로그인 — {' · '.join(parts)}. 필요하면 `{' '.join(login_cmd)} <이름>` 을 직접 실행하세요.")
    finally:
        os.close(fd)


def main(agent, list_pending, login_cmd):
    """훅 진입점. 어떤 예외도 세션을 멈추지 않는다."""
    try:
        if not allowed(agent):
            return
        ok, _reason = attended(agent, hook_input())
        if not ok:
            return
        pending = list_pending()
        if pending is None:
            notify(f"MCP 로그인 상태 확인에 실패했습니다. `{agent} mcp list` 로 확인하세요.")
            return
        run(agent, pending, login_cmd)
    except Exception:
        return
