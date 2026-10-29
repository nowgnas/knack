"""knack 훅이 함께 쓰는 셸 명령 파서.

hook.json 이 없는 폴더라 훅으로 설치되지 않는다. 훅 스크립트가 자기 위치 기준으로 import 한다.
셸 문법 전체를 해석하지 않는다. 따옴표·히어독을 데이터로 보고, 래퍼와 변수 대입을 걷어내
"실제로 실행되는 명령"을 찾는 데 필요한 만큼만 다룬다.
"""
import os
import re

WRAPPERS = {"sudo", "command", "nohup", "time", "exec", "env", "xargs", "nice"}
WRAPPER_ARG_OPTS = {"-u", "-g", "-I", "-n", "-L", "-P", "-d", "-s", "-E"}  # 다음 토큰을 값으로 받는 래퍼 옵션
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*=")
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)(\w+)\1")  # <<< 는 히어스트링이라 본문이 없다
SEGMENT = re.compile(r"\|\||&&|[;|\n]")


def strip_heredocs(cmd):
    """히어독 본문을 걷어낸다. 본문은 데이터라 그 안의 명령·경로를 실행으로 읽으면 안 된다
    (스킬·문서에 예시 명령을 적는 작업이 전부 막힌다). 히어독을 시작한 줄은 남긴다."""
    return split_heredocs(cmd)[0]


def split_heredocs(cmd):
    """(본문을 걷어낸 명령, [(히어독을 시작한 줄, 본문)]) 을 돌려준다."""
    out, bodies, marker, start, body = [], [], None, "", []
    for line in cmd.split("\n"):
        if marker is not None:
            if line.strip() == marker:
                bodies.append((start, "\n".join(body)))
                marker, body = None, []
            else:
                body.append(line)
            continue
        out.append(line)
        m = HEREDOC.search(line)
        if m:
            marker, start = m.group(2), line
    if marker is not None:
        bodies.append((start, "\n".join(body)))
    return "\n".join(out), bodies


def scan(seg):
    """세그먼트를 훑어 (실행 토큰, 리다이렉트 대상) 을 돌려준다.

    따옴표 안은 토큰 하나로 묶어 그 안의 '>' 나 명령 이름을 실행으로 보지 않는다.
    '>' 바로 뒤의 토큰만 쓰기 대상이다 — 따옴표로 감싼 경로도 대상으로 잡는다.
    """
    toks, targets = words(seg)
    return unwrap(toks), targets


def words(seg):
    """세그먼트를 (토큰, 리다이렉트 대상) 으로 나눈다. 래퍼·변수 대입은 그대로 둔다."""
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
    return toks, targets


def unwrap(toks):
    """sudo·env·xargs 같은 래퍼와 그 옵션, 변수 대입을 걷어내 실제로 실행되는 명령부터 돌려준다."""
    return split_prefix(toks)[1]


def split_prefix(toks):
    """([앞쪽 변수 대입 VAR=값], 실제 명령부터의 토큰). env 래퍼 뒤의 대입도 모은다."""
    assigns, i = [], 0
    while i < len(toks):
        if ASSIGN.match(toks[i]):
            assigns.append(toks[i])
            i += 1
        elif os.path.basename(toks[i]) in WRAPPERS:
            i += 1
            while i < len(toks) and toks[i].startswith("-"):
                i += 2 if toks[i] in WRAPPER_ARG_OPTS else 1
        else:
            break
    return assigns, toks[i:]


def segments(cmd):
    """; && || | & 줄바꿈으로 나누되 따옴표·$( )·백틱 안은 자르지 않는다.

    연결 문자열(`"Server=x;Database=y"`)처럼 따옴표 안의 ; 가 흔한 명령을 다루는 훅용.
    (조각, 앞 구분자) 목록을 돌려준다. 앞 구분자가 '|' 면 파이프로 표준 입력을 받는 조각이다.
    """
    out, cur, quote, depth, i, prev = [], "", None, 0, 0, ""
    while i < len(cmd):
        c = cmd[i]
        if quote:
            cur += c
            if c == "\\" and quote == '"' and i + 1 < len(cmd):
                cur += cmd[i + 1]
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c == "\\" and i + 1 < len(cmd):
            cur += cmd[i:i + 2]
            i += 2
            continue
        if c in "'\"`":
            quote = c
            cur += c
            i += 1
            continue
        if cmd.startswith("$(", i):
            depth += 1
            cur += "$("
            i += 2
            continue
        if c == ")" and depth:
            depth -= 1
            cur += c
            i += 1
            continue
        if depth == 0:
            two = cmd[i:i + 2]
            if two in ("&&", "||"):
                out.append((cur, prev))
                cur, prev = "", two
                i += 2
                continue
            if c in ";\n|&" and not (c == "&" and cmd[i - 1:i] in "<>" and i) and not cmd.startswith("&>", i):
                out.append((cur, prev))
                cur, prev = "", c
                i += 1
                continue
        cur += c
        i += 1
    out.append((cur, prev))
    return [(s, p) for s, p in out if s.strip()]
