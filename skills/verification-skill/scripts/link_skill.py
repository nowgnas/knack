#!/usr/bin/env python3
"""verify-<앱> 스킬의 정본(.agents/skills/<이름>)을 .claude/skills/<이름> 으로 잇고, 이어진 상태를 확인한다.

  link_skill.py link  <레포> <이름> [--copy]   상대 심볼릭 링크. 실패하거나 --copy 면 복사 + sha256 목록
  link_skill.py check <레포> <이름>            링크가 정본을 가리키는지, 복사본이 정본과 같은지
종료 코드: 0 정상 · 1 표류(깨진 링크, 내용 다름, 정본 없음) · 2 사용법 오류·덮어쓰기 거부
"""
import hashlib
import os
import shutil
import sys
from pathlib import Path

MANIFEST = ".knack-copy.sha256"


def tree_hashes(root):
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != MANIFEST:
            out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def paths(repo, name):
    repo = Path(repo).resolve()
    return repo / ".agents" / "skills" / name, repo / ".claude" / "skills" / name


def write_manifest(src, dst):
    lines = [f"{h}  {rel}" for rel, h in tree_hashes(src).items()]
    (dst / MANIFEST).write_text("\n".join(lines) + "\n", encoding="utf-8")


def link(repo, name, copy=False):
    src, dst = paths(repo, name)
    if not (src / "SKILL.md").is_file():
        print(f"정본 없음: {src}/SKILL.md")
        return 1
    if dst.is_symlink() or dst.exists():
        is_ours = dst.is_symlink() or (dst / MANIFEST).is_file()
        if not is_ours:
            print(f"덮어쓰지 않음: {dst} 가 이미 있고 이 스크립트가 만든 것이 아니다")
            return 2
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not copy:
        try:
            os.symlink(os.path.relpath(src, dst.parent), dst, target_is_directory=True)
            print(f"링크: {dst} -> {os.readlink(dst)}")
            return 0
        except (OSError, NotImplementedError) as e:
            print(f"심볼릭 링크 실패({e.__class__.__name__}) — 복사로 대신한다")
    shutil.copytree(src, dst)
    write_manifest(src, dst)
    print(f"복사: {dst} (sha256 목록 {MANIFEST}). 정본을 고치면 link 를 다시 돌린다")
    return 0


def check(repo, name):
    src, dst = paths(repo, name)
    if not (src / "SKILL.md").is_file():
        print(f"표류: 정본 없음 {src}/SKILL.md")
        return 1
    if dst.is_symlink():
        if dst.resolve() == src.resolve():
            print(f"정상: 링크 {dst} -> {os.readlink(dst)}")
            return 0
        print(f"표류: 링크가 정본을 가리키지 않음 ({os.readlink(dst)})")
        return 1
    if not dst.is_dir():
        print(f"표류: {dst} 없음 — link 를 돌린다")
        return 1
    a, b = tree_hashes(src), tree_hashes(dst)
    diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    if diff:
        print("표류: 복사본이 정본과 다름 — " + ", ".join(diff))
        return 1
    print(f"정상: 복사본 {dst} 가 정본과 같음 (파일 {len(a)}개)")
    return 0


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 3 or args[0] not in ("link", "check"):
        print(__doc__)
        return 2
    cmd, repo, name = args
    if "/" in name or "\\" in name or name in ("", ".", ".."):
        print("이름은 폴더 이름 하나여야 한다 (예: verify-order-api)")
        return 2
    return link(repo, name, "--copy" in argv) if cmd == "link" else check(repo, name)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
