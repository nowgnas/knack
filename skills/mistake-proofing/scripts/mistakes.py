#!/usr/bin/env python3
"""레포에 커밋된 docs/mistakes.md 원장에서 mistake:<slug> 발생을 세어 재발을 판정한다.

  mistakes.py list  <레포>   태그별 횟수와 버그 기록
  mistakes.py check <레포>   2회 이상 난 태그가 docs/enforcement.md 표에 증명된 행으로 없으면 exit 1
원장 행: | 날짜(YYYY-MM-DD) | `mistake:<slug>` | 한 줄 요약 | 버그 기록(PR·이슈·커밋·BUGFIX.md 경로) | — 한 행이 한 번의 발생이다.
같은 태그·같은 버그 기록의 행은 한 번으로 센다. .design/ 의 BUGFIX.md 는 커밋되지 않으므로 세지 않는다(맥락용).
enforcement 표의 행: | 태그 | 룰 | 강제 수단 | 실행 명령 | 과거 실패 증명 | — 빈 칸·<자리표시자>·"미증명"이면 강제된 것으로 보지 않는다.
"강제 불가 — 사유"(판단이 필요해 구조로 못 막는 경우)는 기록된 것으로 인정한다.
파일은 UTF-8(BOM 허용) 또는 BOM 있는 UTF-16 이어야 한다.
종료 코드: 0 정상 · 1 강제 수단 없는 재발 · 2 사용법 오류·읽을 수 없는 파일·원장 형식 오류
"""
import re
import sys
from pathlib import Path

# 경계는 ASCII 로만 본다: "mistake:missing-tx가" 처럼 한국어 조사가 바로 붙어도 태그로 센다.
TAG = re.compile(r"(?<![A-Za-z0-9_-])mistake:([a-z0-9][a-z0-9-]*[a-z0-9]|[a-z0-9])(?![A-Za-z0-9_-])", re.IGNORECASE)
PLACEHOLDER = re.compile(r"^<.*>$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LEDGER = ("docs", "mistakes.md")
NO_RECORD = {"", "-", "—"}
REPEAT = 2


class Unreadable(Exception):
    pass


def read_text(p):
    try:
        data = p.read_bytes()
    except OSError as e:
        raise Unreadable(f"{p}: 읽을 수 없다 ({e.strerror or e})")
    try:
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            return data.decode("utf-16")
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise Unreadable(f"{p}: UTF-8/UTF-16(BOM) 로 읽을 수 없다 ({e.reason}) — 인코딩을 바꾼다")


def tags_in(text):
    return {t.lower() for t in TAG.findall(text)}


def cells_of(line):
    """표 한 줄의 칸. 칸 안의 \\| 는 구분자가 아니다."""
    line = line.strip()
    return [c.strip() for c in re.split(r"(?<!\\)\|", line[1:-1] if line.endswith("|") else line[1:])]


def collect(repo):
    """태그 → 발생(날짜 · 버그 기록) 목록. 원장 표의 둘째 칸에 태그가 있는 행만 센다."""
    doc = repo.joinpath(*LEDGER)
    out, seen = {}, set()
    if not doc.is_file():
        if doc.is_symlink() or doc.exists():
            raise Unreadable(f"{doc}: 원장이 일반 파일이 아니다(깨진 링크·폴더)")
        return out
    for no, line in enumerate(read_text(doc).splitlines(), 1):
        if not line.strip().startswith("|"):
            continue
        cells = cells_of(line)
        tags = tags_in(cells[1]) if len(cells) > 1 else set()
        if not tags:
            continue  # 머리글·구분선·자리표시자 행
        where = f"{'/'.join(LEDGER)}:{no}"
        if len(cells) != 4:
            raise Unreadable(f"{where}: 열이 4개가 아니다 (날짜 | 태그 | 요약 | 버그 기록, 칸 안의 | 는 \\| )")
        if len(tags) != 1:
            raise Unreadable(f"{where}: 한 행에 태그는 하나만 적는다")
        if not DATE.match(cells[0]):
            raise Unreadable(f"{where}: 날짜는 YYYY-MM-DD")
        slug, record = tags.pop(), cells[3]
        if record not in NO_RECORD:
            if (slug, record) in seen:
                continue  # 같은 버그를 두 번 적은 행
            seen.add((slug, record))
        out.setdefault(slug, []).append(f"{cells[0]} {record if record not in NO_RECORD else '(기록 없음)'}")
    return out


def row_state(cells):
    """표 한 행의 상태: 증명됨 · 강제 불가 · 미완성(사유)."""
    if len(cells) != 5:
        return "미완성(열 개수가 5가 아님 — 칸 안의 | 는 \\| 로 적는다)"
    rule, means, cmd, proof = cells[1:5]
    if "강제 불가" in means:
        m = re.search(r"강제 불가\s*[—–-]+\s*(\S.*)", means)
        if rule and not PLACEHOLDER.match(rule.strip("`")) and m and not PLACEHOLDER.match(m.group(1).strip("` ")):
            return "강제 불가"
        return "미완성(강제 불가 사유 없음)"
    for name, v in (("룰", rule), ("강제 수단", means), ("실행 명령", cmd), ("과거 실패 증명", proof)):
        if not v or PLACEHOLDER.match(v.strip("`")):
            return f"미완성({name} 비어 있음)"
    if "미증명" in proof:
        return "미완성(미증명)"
    return "증명됨"


def enforced(repo):
    """태그 → 상태. 표의 첫 칸에 태그가 있는 행만 본다(설명 문장 속 언급은 세지 않는다)."""
    doc = repo / "docs" / "enforcement.md"
    out = {}
    if not doc.is_file():
        return out
    for line in read_text(doc).splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = cells_of(line)
        if len(cells) < 5:
            continue
        state = row_state(cells)
        for slug in tags_in(cells[0]):
            if out.get(slug) not in ("증명됨", "강제 불가"):
                out[slug] = state
    return out


def accepted(state):
    return state in ("증명됨", "강제 불가")


def main(argv):
    if len(argv) != 2 or argv[0] not in ("list", "check"):
        print(__doc__)
        return 2
    repo = Path(argv[1]).resolve()
    if not repo.is_dir():
        print(f"레포 폴더가 아니다: {repo}")
        return 2
    try:
        tags, done = collect(repo), enforced(repo)
    except Unreadable as e:
        print("읽기·형식 오류: " + str(e))
        return 2
    if argv[0] == "list":
        if not tags:
            print("기록 없음 (bug-fix 가 docs/mistakes.md 에 mistake:<slug> 행을 한 줄씩 추가한다)")
        for slug, hits in sorted(tags.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            if accepted(done.get(slug)):
                mark = done[slug]
            elif len(hits) >= REPEAT:
                mark = "재발 — 강제 필요" + (f" (표: {done[slug]})" if slug in done else "")
            else:
                mark = "1회"
            print(f"mistake:{slug}\t{len(hits)}회\t{mark}\t{'; '.join(hits)}")
        return 0
    missing = sorted(s for s, f in tags.items() if len(f) >= REPEAT and not accepted(done.get(s)))
    for slug in missing:
        why = f"표의 행이 {done[slug]}" if slug in done else "docs/enforcement.md 표에 행이 없다"
        print(f"강제 수단 없음: mistake:{slug} ({len(tags[slug])}회: {'; '.join(tags[slug])}) — {why}")
    if missing:
        return 1
    print(f"정상: 재발한 태그가 모두 docs/enforcement.md 에 있다 (태그 {len(tags)}개)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
