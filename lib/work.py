"""knack work — 과제 문서(.design/<slug>/) 위치와 진행 기록.

과제 문서는 커밋되지 않으므로 worktree 마다 따로 생기면 다른 세션·에이전트가 볼 수 없다.
그래서 위치를 메인 worktree 의 .design/ 하나로 정하고, 진행 상황은 PROGRESS.md 에 한 줄씩 덧붙인다.
덧붙이기만 하므로 여러 에이전트가 동시에 써도 서로의 기록을 덮어쓰지 않는다.
"""
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path

SLUG_RE = re.compile(r"^[0-9A-Za-z가-힣][0-9A-Za-z가-힣._-]*$")
EVENTS = {"시작": "start", "완료": "done", "막힘": "blocked", "인계": "handoff",
          "승인": "approved", "결정": "decision", "메모": "note"}
ALIASES = {v: k for k, v in EVENTS.items()}
CLOSING = ("완료", "막힘", "인계")
DOCS = ("PLAN.md", "BUGFIX.md", "GATES.md", "REVIEW.md")
STATE_RE = re.compile(r"^>.*?상태:\s*([^·\n]+)", re.M)
STEP_RE = re.compile(r"^\s*- \[([ xX])\] (.+?)\s*$")
HEADER = ("# {slug} 진행 기록\n\n"
          "> `knack work log {slug} <사건> \"<메모>\"` 가 한 줄씩 덧붙인다. 지난 줄은 고치지 않는다.\n"
          "> 현재 상태: `knack work status {slug}`\n\n"
          "| 시각 | 누가 | 사건 | 단계 | 메모 |\n|---|---|---|---|---|\n")


def git(cwd, *args):
    try:
        p = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    except OSError:
        return ""
    return p.stdout.strip() if p.returncode == 0 else ""


def local_dir(cwd):
    top = git(cwd, "rev-parse", "--show-toplevel")
    return (Path(top) if top else Path(cwd)) / ".design"


def override(cwd):
    """다른 clone·PC 와 나누는 폴더: KNACK_WORK_DIR, 없으면 레포에 저장한 git config knack.workdir"""
    return os.environ.get("KNACK_WORK_DIR") or git(cwd, "config", "--get", "knack.workdir")


def base_dir(cwd):
    """KNACK_WORK_DIR → git config knack.workdir → 메인 worktree 의 .design → 이 폴더의 .design"""
    if override(cwd):
        return Path(override(cwd)).expanduser()
    common = git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common and Path(common).name == ".git":
        return Path(common).parent / ".design"
    return local_dir(cwd)


def ensure(base, shared=False):
    base.mkdir(parents=True, exist_ok=True)
    ignore = base / ".gitignore"
    if not ignore.exists() and not shared:
        ignore.write_text("*\n", encoding="utf-8")


def outside_dir(cwd):
    """과제 문서 폴더가 이 worktree 밖이면 그 경로 — 샌드박스에 쓰기 허용 폴더로 넘길 때 쓴다."""
    base, top = base_dir(cwd), git(cwd, "rev-parse", "--show-toplevel")
    if not top or base == Path(top) / ".design":
        return None
    return base


def task_dir(cwd, slug, create=False):
    if not SLUG_RE.match(slug):
        sys.exit(f"slug 형식 오류: {slug!r} — 영문·숫자·한글·._- 만 쓴다 (예: ORDER-123-cancel)")
    base = base_dir(cwd)
    if create:
        try:
            ensure(base, shared=bool(override(cwd)))
            (base / slug).mkdir(exist_ok=True)
        except OSError as e:
            local = local_dir(cwd)
            if local == base:
                sys.exit(f"과제 폴더를 만들 수 없음: {base / slug} ({e})")
            print(f"⚠ 공유 폴더에 쓸 수 없어 이 worktree 에만 기록한다: {e}\n"
                  f"  샌드박스가 막았다면 쓰기 허용 폴더에 추가한다: codex --add-dir {base} (knack run 은 자동으로 넣는다)\n"
                  f"  나중에 쓸 수 있는 세션에서 knack work sync {slug} 로 공유 폴더에 합친다.", file=sys.stderr)
            base = local
            ensure(base)
            (base / slug).mkdir(exist_ok=True)
    return base / slug


def who(cwd):
    agent = os.environ.get("KNACK_AGENT")
    if not agent:
        if os.environ.get("CLAUDECODE"):
            agent = "claude"
        elif any(k.startswith("CODEX_") for k in os.environ):
            agent = "codex"
        else:
            agent = os.environ.get("USER") or "agent"
        # 같은 worktree 에서 도는 두 세션을 구분한다. 세션 ID 를 알 수 없는 에이전트는 이름만 남는다.
        session = next((os.environ[k] for k in ("CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "CODEX_SESSION_ID")
                        if os.environ.get(k)), "")
        if session:
            agent += "#" + re.sub(r"[^0-9A-Za-z]", "", session)[:4]
    top = git(cwd, "rev-parse", "--show-toplevel")
    where = Path(top).name if top else Path(cwd).name
    branch = git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    return f"{agent}@{where}" + (f":{branch}" if branch else "")


def cell(text):
    return re.sub(r"\s+", " ", str(text)).replace("|", "\\|").strip()


def read_log(folder):
    path = folder / "PROGRESS.md"
    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("| 2"):
            continue
        cols = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cols) == 5:
            rows.append(dict(zip(("at", "who", "event", "step", "note"), cols)))
    return rows


def active(rows):
    """시작한 뒤 같은 사람이 같은 단계를 닫지(완료·막힘·인계) 않은 줄"""
    open_ = {}
    for r in rows:
        key = (r["who"], r["step"])
        if r["event"] == "시작":
            open_[key] = r
        elif r["event"] in CLOSING:
            open_.pop(key, None)
    return list(open_.values())


def age_note(at):
    """시작만 있고 닫히지 않은 기록이 오래됐으면 끊긴 세션일 수 있다."""
    try:
        hours = (datetime.datetime.now() - datetime.datetime.strptime(at, "%Y-%m-%d %H:%M")).total_seconds() / 3600
    except ValueError:
        return ""
    return f" (⚠ {int(hours // 24)}일 전 — 끊긴 세션일 수 있다. 사용자에게 확인하고 인계로 닫는다)" if hours >= 24 else ""


def summary(folder):
    docs = [d for d in DOCS if (folder / d).is_file()]
    state, done, total, todo = "", 0, 0, []
    main = next((folder / d for d in ("PLAN.md", "BUGFIX.md") if (folder / d).is_file()), None)
    if main:
        text = main.read_text(encoding="utf-8", errors="replace")
        m = STATE_RE.search(text)
        if m and "|" not in m.group(1):
            state = m.group(1).strip().strip("*")
        in_steps = False
        for line in text.splitlines():
            if line.startswith("## "):
                in_steps = line.startswith("## 7.")
                continue
            m = STEP_RE.match(line) if in_steps else None
            if m:
                total += 1
                if m.group(1).strip():
                    done += 1
                else:
                    todo.append(m.group(2))
    return {"docs": docs, "state": state, "done": done, "total": total, "todo": todo}


def tasks(cwd):
    base, local = base_dir(cwd), local_dir(cwd)
    found = []
    for root in ([base] if base == local else [base, local]):
        if not root.is_dir():
            continue
        for d in sorted(p for p in root.iterdir() if p.is_dir()):
            if any((d / f).is_file() for f in DOCS + ("PROGRESS.md",)):
                found.append((d, root != base))
    return base, found


def open_tasks(cwd, max_age_days=30):
    """끝나지 않았고 최근에 손댄 과제를 한 줄 요약으로 — 세션 시작 훅이 쓴다."""
    base, found = tasks(cwd)
    now, out = datetime.datetime.now().timestamp(), []
    for d, local_only in found:
        s, rows = summary(d), read_log(d)
        if "완료" in s["state"] or (not s["state"] and rows and rows[-1]["event"] == "완료"):
            continue
        newest = max((f.stat().st_mtime for f in d.iterdir() if f.is_file()), default=0)
        if now - newest > max_age_days * 86400:
            continue
        line = f"{d.name} — 상태 {s['state'] or '미기재'}"
        if s["total"]:
            line += f" · 구현 순서 {s['done']}/{s['total']}"
        if rows:
            line += f" · 마지막 {rows[-1]['at']} {rows[-1]['who']} {rows[-1]['event']} {rows[-1]['step']}: {rows[-1]['note'][:80]}"
        busy = sorted({r["who"] for r in active(rows)})
        if busy:
            line += " · 작업 중 " + ", ".join(busy)
        if local_only:
            line += " (이 worktree 에만 있음 — knack work sync)"
        out.append(line)
    return base, out


def cmd_path(a, cwd):
    print(task_dir(cwd, a.slug, create=True) if a.slug else base_dir(cwd))


def cmd_log(a, cwd):
    event = ALIASES.get(a.event, a.event)
    if event not in EVENTS:
        sys.exit(f"사건은 {' · '.join(EVENTS)} 중 하나 (영문: {' · '.join(ALIASES)})")
    folder = task_dir(cwd, a.slug, create=True)
    me, step = a.who or who(cwd), cell(a.step) or "-"
    if event == "시작":
        for r in active(read_log(folder)):
            if r["step"] == step and r["who"] != me:
                print(f"⚠ {r['who']} 가 같은 단계({step})를 작업 중이다 ({r['at']} 시작: {r['note']}){age_note(r['at'])}. "
                      "겹치는 파일을 고치기 전에 사용자에게 확인한다.", file=sys.stderr)
    path = folder / "PROGRESS.md"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"| {now} | {cell(me)} | {event} | {step} | {cell(a.note)} |\n"
    if not path.exists():
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(HEADER.format(slug=a.slug))
        except FileExistsError:
            pass
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)
    print(f"{path}: {line.strip()}")


def cmd_list(a, cwd):
    base, found = tasks(cwd)
    if not found:
        print(f"과제 문서 없음 — {base}")
        return
    print(f"과제 문서: {base}")
    for d, local_only in found:
        s, rows = summary(d), read_log(d)
        steps = f"{s['done']}/{s['total']}" if s["total"] else "-"
        last = f"{rows[-1]['at']} {rows[-1]['who']} {rows[-1]['event']} {rows[-1]['step']}" if rows else "기록 없음"
        busy = " · 작업 중 " + ", ".join(sorted({r["who"] for r in active(rows)})) if active(rows) else ""
        mark = " (이 worktree 에만 있음)" if local_only else ""
        print(f"  {d.name}{mark} — 상태 {s['state'] or '미기재'} · 구현 순서 {steps} · {' '.join(s['docs']) or '문서 없음'}"
              f"\n      마지막: {last}{busy}")


def cmd_status(a, cwd):
    if not a.slug:
        return cmd_list(a, cwd)
    folder = task_dir(cwd, a.slug)
    if not folder.is_dir():
        local = local_dir(cwd) / a.slug
        if not local.is_dir():
            sys.exit(f"과제 없음: {folder} — 목록은 knack work list")
        folder = local
        print("⚠ 이 worktree 에만 있는 문서다. 다른 worktree 에서는 보이지 않는다.")
    s, rows = summary(folder), read_log(folder)
    print(f"{a.slug} — {folder}")
    print(f"  문서: {' '.join(s['docs']) or '없음'} · 상태: {s['state'] or '미기재'}"
          + (f" · 구현 순서 {s['done']}/{s['total']}" if s["total"] else ""))
    approvals = [r for r in rows if r["event"] == "승인"]
    print("  설계 승인: " + (f"{approvals[-1]['at']} {approvals[-1]['note']}" if approvals else "기록 없음 — 구현 전에 확인"))
    for r in active(rows):
        print(f"  작업 중: {r['who']} · {r['step']} · {r['at']} 부터 — {r['note']}{age_note(r['at'])}")
    if rows and rows[-1]["event"] in ("막힘", "인계"):
        print(f"  ⚠ 마지막 기록이 {rows[-1]['event']}: {rows[-1]['note']}")
    if s["todo"]:
        print("  남은 구현 순서:")
        for t in s["todo"][:10]:
            print(f"    - [ ] {t}")
    if rows:
        print(f"  최근 기록 (전체 {len(rows)}줄, {folder / 'PROGRESS.md'}):")
        for r in rows[-a.tail:]:
            print(f"    {r['at']} {r['who']} [{r['event']}] {r['step']} — {r['note']}")
    else:
        print("  진행 기록 없음 — knack work log 로 남긴다")


def cmd_sync(a, cwd):
    """이 worktree 에만 남은 과제 문서를 공유 폴더로 합친다. 진행 기록은 없는 줄만 덧붙이고, 다른 파일은 덮어쓰지 않는다."""
    base, local = base_dir(cwd), local_dir(cwd)
    if base == local or not local.is_dir():
        print("합칠 것 없음 — 이 worktree 에만 있는 과제 문서가 없다")
        return
    conflicts = 0
    for src in sorted(p for p in local.iterdir() if p.is_dir() and (not a.slug or p.name == a.slug)):
        dst = base / src.name
        ensure(base, shared=bool(override(cwd)))
        dst.mkdir(exist_ok=True)
        for f in sorted(p for p in src.rglob("*") if p.is_file()):
            target = dst / f.relative_to(src)
            if f.name == "PROGRESS.md" and target.exists():
                have = set(target.read_text(encoding="utf-8").splitlines())
                new = [l for l in f.read_text(encoding="utf-8").splitlines() if l.startswith("| 2") and l not in have]
                with open(target, "a", encoding="utf-8") as out:
                    out.writelines(l + "\n" for l in new)
                print(f"  합침 {target} (+{len(new)}줄)")
                f.unlink()
            elif target.exists() and target.read_bytes() != f.read_bytes():
                conflicts += 1
                print(f"  ✗ 충돌 {target} — 내용이 다르다. {f} 를 보고 직접 합친다")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    target.write_bytes(f.read_bytes())
                print(f"  옮김 {target}")
                f.unlink()
        for d in sorted((p for p in src.rglob("*") if p.is_dir()), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
        if not any(src.iterdir()):
            src.rmdir()
    sys.exit(1 if conflicts else 0)


def cmd_work(a):
    cwd = Path.cwd()
    {"path": cmd_path, "log": cmd_log, "list": cmd_list, "status": cmd_status, "sync": cmd_sync}[a.action](a, cwd)
