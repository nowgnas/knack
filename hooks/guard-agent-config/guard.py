#!/usr/bin/env python3
"""PreToolUse 훅: 에이전트 설정 폴더(스킬·서브에이전트)에 직접 쓰는 것을 막고 하네스로 안내한다.

Claude Code(Write/Edit/MultiEdit/Bash)와 Codex(shell, apply_patch)의 입력 형식을 모두 처리한다.
판단할 수 없는 입력은 통과시킨다(fail-open). 에이전트 작업을 훅 오류로 멈추지 않기 위해서다.
"""
import json
import os
import re
import shlex
import sys

HOME_FORMS = {os.path.expanduser("~"), os.path.realpath(os.path.expanduser("~"))}
KNACK = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", ".."))
PROTECTED = (".claude/skills", ".claude/agents", ".agents/skills", ".codex/skills", ".copilot/skills")
PREFIXES = sorted({h + "/" for h in HOME_FORMS} | {"~/", "$HOME/", "${HOME}/"})

WRITE_CMD = re.compile(
    r"(^|[\s;&|(])(cp|mv|ln|rsync|install|mkdir|rm|rmdir|touch|tee|unzip|tar|curl|wget|git\s+clone)\b")
REDIRECT = re.compile(r">")
HARMLESS_REDIRECT = re.compile(r"\d*>\s*/dev/null|\d*>&\d")
SKILLS_CLI = re.compile(r"\bskills?\s+(add|install)\b")
SEGMENT = re.compile(r"\|\||&&|[;|\n]")
KNACK_CMD = re.compile(r"^\s*\(?\s*(knack\s|\S*/install\.sh\b)")
CD = re.compile(r"""^\s*cd\s+("[^"]*"|'[^']*'|[^\s;&|]+)\s*$""")
PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.M)

GUIDE = ("하네스 관리 대상 경로입니다: {path}\n"
         "스킬·서브에이전트는 에이전트 설정 폴더에 직접 설치하지 않고 하네스에 추가합니다.\n"
         "- 현재 목록·중복 확인: knack list --all\n"
         "- 외부 스킬 추가: knack add skill <경로|git URL> → knack install\n"
         "- 새로 만들기: knack new skill <이름>\n"
         "하네스 밖 설치가 꼭 필요하면 사용자가 직접 실행하도록 안내하세요.")


def deny(path):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": GUIDE.format(path=path)}}, ensure_ascii=False))
    sys.exit(0)


def inside(path, root):
    return path == root or path.startswith(root + os.sep)


def protected_file(path, cwd):
    """파일 경로가 보호 폴더 안이면서 하네스로 이어지지 않으면 그 경로를 돌려준다."""
    full = os.path.expanduser(path)
    if not os.path.isabs(full):
        full = os.path.join(cwd or os.getcwd(), full)
    real = os.path.realpath(full)
    if inside(real, KNACK):
        return None
    for home in HOME_FORMS:
        for rel in PROTECTED:
            root = os.path.join(home, rel)
            if inside(os.path.normpath(full), root) or inside(real, os.path.realpath(root)):
                return full
    return None


def protected_in_command(cmd, cwd):
    for prefix in PREFIXES:
        for rel in PROTECTED:
            for m in re.finditer(re.escape(prefix + rel) + r"(/[^\s'\";|&)]*)?", cmd):
                path = m.group(0)
                for form in ("~/", "$HOME/", "${HOME}/"):
                    if path.startswith(form):
                        path = os.path.join(os.path.expanduser("~"), path[len(form):])
                if protected_file(path, cwd):
                    return m.group(0)
    return None


def expand(path, cwd):
    path = path.strip("'\"")
    for form in ("$HOME/", "${HOME}/"):
        if path.startswith(form):
            path = "~/" + path[len(form):]
    full = os.path.expanduser(path)
    return os.path.normpath(full if os.path.isabs(full) else os.path.join(cwd or os.getcwd(), full))


def relative_hit(seg, cwd):
    """상대 경로 인자가 보호 폴더를 가리키면 그 경로 (작업 폴더 자체가 보호 폴더인 경우 포함)"""
    try:
        words = shlex.split(seg)
    except ValueError:
        return None
    for w in words[1:]:
        if not w or w.startswith(("-", "/", "~", "$")):
            continue
        hit = protected_file(w, cwd)
        if hit:
            return hit
    return None


def check_command(cmd, cwd):
    # ; && || | 로 나눈 조각마다 판정한다. knack 명령인 조각만 면제하고, cd 는 뒤 조각의 작업 폴더를 바꾼다
    for seg in SEGMENT.split(cmd):
        if not seg.strip() or KNACK_CMD.match(seg):
            continue
        m = CD.match(seg)
        if m:
            cwd = expand(m.group(1), cwd)
            continue
        if SKILLS_CLI.search(seg):
            deny("skills add/install 명령 (에이전트 설정 폴더에 설치됨)")
        if not (WRITE_CMD.search(seg) or REDIRECT.search(HARMLESS_REDIRECT.sub("", seg))):
            continue
        hit = protected_in_command(seg, cwd) or relative_hit(seg, cwd)
        if hit:
            deny(hit)


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    tool_input = payload.get("tool_input") or {}
    cwd = payload.get("cwd") or ""
    if not isinstance(tool_input, dict):
        tool_input = {"input": tool_input}
    for key, value in tool_input.items():
        if isinstance(value, list) and key == "command":
            value = " ".join(str(v) for v in value)
        if not isinstance(value, str):
            continue
        if "path" in key:
            hit = protected_file(value, cwd)
            if hit:
                deny(hit)
        elif key in ("command", "cmd"):
            check_command(value, cwd)
        elif "*** Begin Patch" in value:
            for path in PATCH_FILE.findall(value):
                hit = protected_file(path.strip(), cwd)
                if hit:
                    deny(hit)


if __name__ == "__main__":
    main()
