#!/usr/bin/env python3
"""레포의 BUGFIX.md 에서 mistake:<slug> 태그를 모아 재발을 판정한다. 상태 파일을 두지 않는다.

  mistakes.py list  <레포>   태그별 횟수와 파일
  mistakes.py check <레포>   2회 이상 난 태그가 docs/enforcement.md 에 없으면 exit 1
종료 코드: 0 정상 · 1 강제 수단 없는 재발 · 2 사용법 오류
"""
import re
import sys
from pathlib import Path

TAG = re.compile(r"(?<![\w-])mistake:([a-z0-9][a-z0-9-]*[a-z0-9]|[a-z0-9])(?![\w-])")
SKIP_DIRS = {".git", "node_modules", "build", "bin", "obj", "target", ".gradle"}
REPEAT = 2


def bugfix_files(repo):
    for p in sorted(repo.rglob("BUGFIX.md")):
        if not SKIP_DIRS.intersection(p.relative_to(repo).parts[:-1]):
            yield p


def collect(repo):
    """태그 → 그 태그를 가진 BUGFIX.md 목록. 한 파일 안의 중복은 한 번으로 센다."""
    out = {}
    for p in bugfix_files(repo):
        text = p.read_text(encoding="utf-8", errors="replace")
        for slug in sorted(set(TAG.findall(text))):
            out.setdefault(slug, []).append(p.relative_to(repo).as_posix())
    return out


def enforced(repo):
    doc = repo / "docs" / "enforcement.md"
    if not doc.is_file():
        return set()
    return set(TAG.findall(doc.read_text(encoding="utf-8", errors="replace")))


def main(argv):
    if len(argv) != 2 or argv[0] not in ("list", "check"):
        print(__doc__)
        return 2
    repo = Path(argv[1]).resolve()
    if not repo.is_dir():
        print(f"레포 폴더가 아니다: {repo}")
        return 2
    tags, done = collect(repo), enforced(repo)
    if argv[0] == "list":
        if not tags:
            print("태그 없음 (BUGFIX.md 의 재발 방지에 mistake:<slug> 를 단다)")
        for slug, files in sorted(tags.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            mark = "강제됨" if slug in done else ("재발 — 강제 필요" if len(files) >= REPEAT else "1회")
            print(f"mistake:{slug}\t{len(files)}회\t{mark}\t{', '.join(files)}")
        return 0
    missing = sorted(s for s, f in tags.items() if len(f) >= REPEAT and s not in done)
    for slug in missing:
        print(f"강제 수단 없음: mistake:{slug} ({len(tags[slug])}회: {', '.join(tags[slug])}) — docs/enforcement.md 에 행을 추가한다")
    if missing:
        return 1
    print(f"정상: 재발한 태그가 모두 docs/enforcement.md 에 있다 (태그 {len(tags)}개)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
