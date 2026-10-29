"""사용자 페르소나 — 에이전트가 되묻거나 잘못 추측할 것을 미리 못 박아 두는 사실 모음.

core 는 매 세션 지시 블록에 주입되므로 짧게(기본 15줄) 유지하고, 결정에 영향을 주는 줄만 둔다.
배경·표·과거 결정처럼 가끔 필요한 것은 detail/<주제>.md 에 두고 `persona show <주제>` 로 읽는다.
core·detail 은 개인 정보라 .gitignore 에 있고, 레포에는 템플릿만 커밋된다.
"""
import os
import re
import shutil
import sys
from pathlib import Path

PERSONA = Path(__file__).resolve().parent.parent / "persona"
CORE = PERSONA / "core.md"
DETAIL = PERSONA / "detail"
TEMPLATE = PERSONA / "templates" / "core.md"
DISABLED = PERSONA / ".disabled"

MAX_LINES = 15  # core 에 허용하는 항목 줄 수 (매 세션 주입 비용)
KEY_RE = re.compile(r"^([a-z][a-z0-9_-]*):[ \t]*(.*)$")
ITEM_RE = re.compile(r"^[ \t]+-[ \t]*(.+)$")
STUB_RE = re.compile(r"<[^>]*>")  # 템플릿의 <...> 자리표시자
LABELS = {"role": "역할", "stack": "스택", "work": "일의 형태", "goals": "목표",
          "defaults": "기본값", "avoid": "피할 것", "team": "팀", "domain": "도메인"}


def fail(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def parse(text):
    """`키: 값` 과 그 아래 `- 항목` 목록을 (키, [값…]) 순서대로 읽는다. 주석·빈 줄은 무시."""
    out = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = KEY_RE.match(line)
        if m:
            out.append((m.group(1), [m.group(2).strip()] if m.group(2).strip() else []))
            continue
        m = ITEM_RE.match(line)
        if m and out:
            out[-1][1].append(m.group(1).strip())
    return out


def load():
    try:
        return parse(CORE.read_text(encoding="utf-8"))
    except OSError:
        return []


def detail_topics():
    if not DETAIL.is_dir():
        return []
    return sorted(p.stem for p in DETAIL.glob("*.md"))


def enabled():
    return not DISABLED.exists()


def problems(entries=None):
    """설정 상태 경고 목록. core 가 없으면 빈 목록(미설정은 문제가 아니다)."""
    if not CORE.is_file():
        return []
    entries = load() if entries is None else entries
    out = []
    if not entries:
        out.append("persona/core.md 에 읽을 항목이 없습니다 (형식: `키: 값`)")
    rows = sum(1 + max(0, len(v) - 1) for _, v in entries)
    if rows > MAX_LINES:
        out.append(f"core 가 {rows}줄입니다 (권장 {MAX_LINES}줄 이내). 결정에 영향 없는 줄을 detail 로 옮기세요")
    for key, values in entries:
        if not values:
            out.append(f"`{key}` 값이 비어 있습니다")
        elif any(STUB_RE.search(v) for v in values):
            out.append(f"`{key}` 가 템플릿 자리표시자 그대로입니다")
    seen = [k for k, _ in entries]
    for key in sorted({k for k in seen if seen.count(k) > 1}):
        out.append(f"`{key}` 가 여러 번 있습니다")
    return out


def render_block():
    """지시 블록에 넣을 텍스트. 미설정·비활성·자리표시자만 있으면 빈 문자열."""
    entries = [(k, v) for k, v in load() if v and not any(STUB_RE.search(x) for x in v)]
    if not entries or not enabled():
        return ""
    lines = ["## 사용자 (knack persona)",
             "아래는 이 사용자에 대해 확인된 사실이다. 작업 목표·기본값을 정할 때 먼저 따르고,"
             " 레포의 실제 코드와 어긋나면 레포를 믿고 사용자에게 알린다."]
    for key, values in entries:
        lines.append(f"- {LABELS.get(key, key)}: {'; '.join(values)}")
    topics = detail_topics()
    if topics:
        lines.append(f"필요할 때 읽는 상세 (`knack persona show <주제>`): {', '.join(topics)}")
    return "\n".join(lines)


# ── 명령 ─────────────────────────────────────
def cmd_persona(a, h):
    {"show": show, "init": init, "set": set_key, "import": import_core, "check": check,
     "enable": lambda x, y: toggle(x, y, True), "disable": lambda x, y: toggle(x, y, False),
     "path": path}[a.action or "show"](a, h)


def path(_a, h):
    print(h.pretty(CORE))
    for topic in detail_topics():
        print(h.pretty(DETAIL / f"{topic}.md"))


def init(a, h):
    if CORE.exists() and not a.force:
        fail(f"이미 있음: {h.pretty(CORE)} (덮어쓰려면 --force)", 2)
    CORE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(TEMPLATE, CORE)
    print(f"생성: {h.pretty(CORE)}\n"
          f"다음: 자리표시자를 실제 사실로 채우고 `knack persona check` → `knack install`")


def show(a, h):
    topic = getattr(a, "topic", None)  # 인자 없는 `knack persona` 도 show 로 온다
    if topic:
        f = DETAIL / f"{topic}.md"
        if not f.is_file():
            fail(f"없는 주제: {topic} (있는 주제: {', '.join(detail_topics()) or '없음'})", 2)
        print(f.read_text(encoding="utf-8").rstrip())
        return
    if not CORE.is_file():
        print(f"페르소나가 없습니다. `knack persona init` 으로 만들고 채우세요. (템플릿: {h.pretty(TEMPLATE)})")
        return
    block = render_block()
    state = "" if enabled() else "  ⚠ 주입 꺼짐 (knack persona enable)"
    print(f"{h.pretty(CORE)}{state}")
    print(block or "  (주입할 항목이 없습니다 — 값이 비었거나 자리표시자 그대로입니다)")
    for line in problems():
        print(f"  ⚠ {line}")


def _write_core(text, h, what):
    CORE.parent.mkdir(parents=True, exist_ok=True)
    CORE.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    print(f"{what}: {h.pretty(CORE)}")
    for line in problems():
        print(f"  ⚠ {line}")
    print("반영: knack install (지시 블록에 다시 씁니다)")


def set_key(a, h):
    """한 항목만 바꾼다. 값에 `;` 가 있으면 목록으로 저장한다."""
    if not KEY_RE.match(f"{a.key}:"):
        fail(f"키는 영문 소문자·숫자·_- 만 사용: {a.key}", 2)
    values = [v.strip() for v in a.value.split(";") if v.strip()]
    if not values:
        fail("값이 비어 있습니다", 2)
    body = f"{a.key}: {values[0]}" if len(values) == 1 else \
        "\n".join([f"{a.key}:"] + [f"  - {v}" for v in values])
    text = CORE.read_text(encoding="utf-8") if CORE.is_file() else ""
    out, replaced, skip = [], False, False
    for line in text.splitlines():
        if skip and (ITEM_RE.match(line) or not line.strip()):
            if ITEM_RE.match(line):
                continue
        skip = False
        m = KEY_RE.match(line)
        if m and m.group(1) == a.key:
            if not replaced:
                out.append(body)
                replaced = True
            skip = True
            continue
        out.append(line)
    if not replaced:
        out.append(body)
    _write_core("\n".join(out), h, "수정" if replaced else "추가")


def import_core(a, h):
    """파일이나 표준 입력으로 core·detail 을 통째로 넣는다 (스크립트 입력 경로)."""
    src = a.file or "-"
    try:
        text = sys.stdin.read() if src == "-" else Path(os.path.expanduser(src)).read_text(encoding="utf-8")
    except OSError as e:
        fail(f"읽을 수 없습니다: {e}")
    if not text.strip():
        fail("입력이 비어 있습니다", 2)
    if a.detail:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", a.detail):
            fail(f"주제는 영문 소문자·숫자·_- 만 사용: {a.detail}", 2)
        DETAIL.mkdir(parents=True, exist_ok=True)
        f = DETAIL / f"{a.detail}.md"
        f.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        print(f"저장: {h.pretty(f)}\n상세는 주입하지 않고 `knack persona show {a.detail}` 로 읽습니다.")
        print("반영: knack install (주제 목록을 지시 블록에 다시 씁니다)")
        return
    if not parse(text):
        fail("`키: 값` 형식의 항목이 없습니다. `knack persona init` 의 템플릿을 참고하세요.", 2)
    _write_core(text, h, "가져옴")


def check(_a, _h):
    if not CORE.is_file():
        print("페르소나 미설정 (knack persona init)")
        return
    issues = problems()
    for line in issues:
        print(f"⚠ {line}")
    entries = load()
    rows = sum(1 + max(0, len(v) - 1) for _, v in entries)
    print(f"항목 {len(entries)}개 · {rows}줄 (권장 {MAX_LINES}줄 이내) · 상세 {len(detail_topics())}개"
          f"{'' if enabled() else ' · 주입 꺼짐'}")
    if not issues:
        print("형식 문제 없음. 내용은 기준으로 직접 점검하세요: "
              "이 줄이 없으면 에이전트가 무엇을 잘못하거나 되묻는가?")
    sys.exit(1 if issues else 0)


def toggle(_a, h, on):
    if on:
        DISABLED.unlink(missing_ok=True)
    else:
        PERSONA.mkdir(parents=True, exist_ok=True)
        DISABLED.write_text("knack persona disable — 주입을 끕니다\n", encoding="utf-8")
    print(f"페르소나 주입 {'켬' if on else '끔'} ({h.pretty(DISABLED)})\n반영: knack install")
