#!/usr/bin/env python3
"""PreToolUse 훅: 하네스가 관리하는 설정(스킬·서브에이전트 폴더, 지시 파일의 knack 블록)에
직접 쓰는 것을 막고 하네스로 안내한다.

Claude Code(Write/Edit/MultiEdit/Bash)와 Codex(shell, apply_patch)의 입력 형식을 모두 처리한다.
판단할 수 없는 입력은 통과시킨다(fail-open). 에이전트 작업을 훅 오류로 멈추지 않기 위해서다.
쓰기 여부는 "명령 이름"과 "리다이렉트 대상"으로만 판정한다. 명령 문자열 안에 보호 경로가
적혀 있다는 이유로 막으면 그 경로를 읽거나 문서에 적는 작업까지 멈춘다.
"""
import json
import os
import re
import sys

HOME_FORMS = {os.path.expanduser("~"), os.path.realpath(os.path.expanduser("~"))}
KNACK = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", ".."))
PROTECTED = (".claude/skills", ".claude/agents", ".agents/skills", ".codex/skills", ".copilot/skills")
# 지시 파일·설정 파일에 install.sh 가 넣는 블록. 마커 안쪽은 생성물이라 직접 고치면 사라진다
BLOCK_MARKERS = (("<!-- knack:start", "<!-- knack:end -->"), ("# knack:start", "# knack:end"))

WRITE_CMDS = {"cp", "mv", "ln", "rsync", "install", "mkdir", "rm", "rmdir", "touch", "tee",
              "unzip", "tar", "curl", "wget", "dd"}
INPLACE_CMDS = {"sed", "perl"}  # -i 가 붙었을 때만 쓰기
GIT_WRITE_SUB = {"clone", "init"}
WRAPPERS = {"sudo", "command", "nohup", "time", "exec"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*=")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")
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

GUIDE_BLOCK = ("하네스가 관리하는 블록이 있는 파일입니다: {path}\n"
               "knack:start … knack:end 사이는 install.sh 가 다시 만들어, 직접 고치면 다음 설치에서 사라집니다.\n"
               "- 룰·페르소나·모델·서브에이전트 변경: 하네스 레포(rules/, persona/, models.json, agents/)를 고치고 knack install\n"
               "- 블록 밖 내용만 바꾸려면 블록을 건드리지 않는 범위로 다시 시도하세요.")


def deny(path, block=False):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": (GUIDE_BLOCK if block else GUIDE).format(path=path)}},
        ensure_ascii=False))
    sys.exit(0)


def inside(path, root):
    return path == root or path.startswith(root + os.sep)


def expand(path, cwd):
    path = path.strip("'\"")
    for form in ("$HOME/", "${HOME}/"):
        if path.startswith(form):
            path = "~/" + path[len(form):]
    full = os.path.expanduser(path)
    return os.path.normpath(full if os.path.isabs(full) else os.path.join(cwd or os.getcwd(), full))


def protected_file(path, cwd):
    """파일 경로가 보호 폴더 안이면서 하네스로 이어지지 않으면 그 경로를 돌려준다."""
    full = expand(path, cwd)
    real = os.path.realpath(full)
    if inside(real, KNACK):
        return None
    for home in HOME_FORMS:
        for rel in PROTECTED:
            root = os.path.join(home, rel)
            if inside(full, root) or inside(real, os.path.realpath(root)):
                return full
    return None


def block_span(path):
    """파일에 하네스 블록이 있으면 (전체 내용, 시작, 끝) 오프셋. 없으면 None."""
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    for start, end in BLOCK_MARKERS:
        i = text.find(start)
        if i < 0:
            continue
        j = text.find(end, i)
        return text, i, (j + len(end) if j >= 0 else len(text))
    return None


def check_path(raw, cwd):
    """쓰기 대상 경로 하나를 판정한다. 보호 폴더면 차단, 블록이 있는 파일이면 블록 차단."""
    hit = protected_file(raw, cwd)
    if hit:
        deny(hit)
    full = expand(raw, cwd)
    if block_span(full):
        deny(full, block=True)


def check_block_edit(full, tool_input, cwd):
    """블록이 있는 파일의 편집: 블록을 건드리는 것만 막는다 (블록 밖 수정은 통과).

    Write 는 통째로 덮어쓰므로 블록을 그대로 담고 있지 않으면 차단한다.
    Edit/MultiEdit 은 old_string 위치가 블록과 겹칠 때만 차단한다.
    """
    span = block_span(full)
    if not span:
        return
    text, i, j = span
    content = tool_input.get("content")
    if isinstance(content, str):
        if text[i:j] not in content:
            deny(full, block=True)
        return
    edits = tool_input.get("edits")
    pairs = edits if isinstance(edits, list) else [tool_input]
    for e in pairs:
        if not isinstance(e, dict):
            continue
        old, new = e.get("old_string"), e.get("new_string")
        if not isinstance(old, str) or not old:
            continue
        if any(mk in old or (isinstance(new, str) and mk in new) for mk, _ in BLOCK_MARKERS):
            deny(full, block=True)
        pos = text.find(old)
        while pos >= 0:
            if pos < j and pos + len(old) > i:
                deny(full, block=True)
            pos = text.find(old, pos + 1)


def strip_heredocs(cmd):
    """히어독 본문을 걷어낸다. 본문은 데이터라 그 안의 명령·경로를 실행으로 읽으면 안 된다
    (스킬·문서에 예시 명령을 적는 작업이 전부 막힌다). 히어독을 시작한 줄은 남긴다."""
    out, marker = [], None
    for line in cmd.split("\n"):
        if marker is not None:
            if line.strip() == marker:
                marker = None
            continue
        out.append(line)
        m = HEREDOC.search(line)
        if m:
            marker = m.group(2)
    return "\n".join(out)


def scan(seg):
    """세그먼트를 훑어 (실행 토큰, 리다이렉트 대상) 을 돌려준다.

    따옴표 안은 토큰 하나로 묶어 그 안의 '>' 나 명령 이름을 실행으로 보지 않는다.
    '>' 바로 뒤의 토큰만 쓰기 대상이다 — 따옴표로 감싼 경로도 대상으로 잡는다.
    """
    toks, targets, cur, redirect, i = [], [], "", False, 0
    while i < len(seg):
        c = seg[i]
        if c in "'\"":
            j = seg.find(c, i + 1)
            cur += seg[i + 1:j if j >= 0 else len(seg)]
            i = (j + 1) if j >= 0 else len(seg)
            continue
        if c.isspace() or c in "><":
            if cur:
                (targets if redirect else toks).append(cur)
                cur, redirect = "", False
            if c == ">":
                i += 2 if seg[i + 1:i + 2] == ">" else 1
                redirect = True
                continue
            i += 1
            continue
        cur += c
        i += 1
    if cur:
        (targets if redirect else toks).append(cur)
    while toks and (toks[0] in WRAPPERS or ASSIGN.match(toks[0])):
        toks = toks[1:]
    return toks, targets


def is_write(words):
    """이 명령이 파일을 쓰는가. 명령 이름으로만 본다 — 읽기 명령의 인자는 막지 않는다."""
    if not words:
        return False
    name = os.path.basename(words[0])
    if name in WRITE_CMDS:
        return True
    if name in INPLACE_CMDS:
        return any(w.startswith("-i") for w in words[1:])
    if name == "git":
        return bool(set(words[1:2]) & GIT_WRITE_SUB)
    return False


def skills_cli(words):
    """`<cli> skill[s] add|install` 처럼 에이전트 설정 폴더에 바로 설치하는 명령인지."""
    for a, b in zip(words, words[1:]):
        if a in ("skill", "skills") and b in ("add", "install"):
            return True
    return False


def check_command(cmd, cwd):
    # ; && || | 로 나눈 조각마다 판정한다. knack 명령인 조각만 면제하고, cd 는 뒤 조각의 작업 폴더를 바꾼다
    for seg in SEGMENT.split(strip_heredocs(cmd)):
        if not seg.strip() or KNACK_CMD.match(seg):
            continue
        m = CD.match(seg)
        if m:
            cwd = expand(m.group(1), cwd)
            continue
        words, targets = scan(seg)
        if words and os.path.basename(words[0]) in SHELLS:  # bash -lc "<명령>" 의 안쪽
            for n, w in enumerate(words[1:], 1):
                if w.startswith("-") and "c" in w.lstrip("-") and n + 1 < len(words):
                    check_command(words[n + 1], cwd)
        if skills_cli(words):
            deny("skills add/install 명령 (에이전트 설정 폴더에 설치됨)")
        for t in targets:  # 리다이렉트는 대상 경로만 본다
            if t.startswith("&") or t == "/dev/null":
                continue
            check_path(t, cwd)
        if not is_write(words):
            continue
        for w in words[1:]:
            if not w or w.startswith("-"):
                continue
            check_path(w, cwd)


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
            for el in value:
                if isinstance(el, str):
                    check_command(el, cwd)
            value = " ".join(str(v) for v in value)
        if not isinstance(value, str):
            continue
        if "path" in key:
            hit = protected_file(value, cwd)
            if hit:
                deny(hit)
            check_block_edit(expand(value, cwd), tool_input, cwd)
        elif key in ("command", "cmd"):
            check_command(value, cwd)
        elif "*** Begin Patch" in value:
            # 패치 본문으로는 블록을 건드리는지 가릴 수 없다 — 블록이 있으면 하네스로 보낸다
            for path in PATCH_FILE.findall(value):
                hit = protected_file(path.strip(), cwd)
                if hit:
                    deny(hit)
                full = expand(path.strip(), cwd)
                if block_span(full):
                    deny(full, block=True)


if __name__ == "__main__":
    main()
