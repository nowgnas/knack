#!/usr/bin/env python3
"""verify-<앱> 스킬의 정본(.agents/skills/<이름>)을 .claude/skills/<이름> 으로 잇고, 이어진 상태를 확인한다.

  link_skill.py link  <레포> <이름> [--copy] [--force]   상대 심볼릭 링크. 실패하거나 --copy 면 복사 + sha256 목록
  link_skill.py check <레포> <이름>                      링크가 정본을 가리키는지, 복사본이 정본과 같은지
  --force: 직접 고친 복사본·다른 곳을 가리키는 링크도 교체한다(이 스크립트가 만든 것이 아닌 폴더는 여전히 거부)
종료 코드: 0 정상 · 1 표류(깨진 링크, 내용 다름, 정본 없음) · 2 사용법 오류·덮어쓰기 거부
"""
import hashlib
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

MANIFEST = ".knack-copy.sha256"
NAME_RE = re.compile(r"^verify-[A-Za-z0-9][A-Za-z0-9._-]*$")
FLAGS = {"--copy", "--force"}


def tree_hashes(root):
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != MANIFEST:
            out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def read_manifest(dst):
    out = {}
    for line in (dst / MANIFEST).read_text(encoding="utf-8").splitlines():
        h, _, rel = line.partition("  ")
        if rel:
            out[rel] = h
    return out


def diff_keys(a, b):
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def paths(repo, name):
    """정본·대상 경로. 중간 폴더가 심볼릭 링크면 레포 밖을 건드릴 수 있으므로 거부한다."""
    repo = Path(repo).resolve()
    for rel in (".agents", ".agents/skills", ".claude", ".claude/skills"):
        if (repo / rel).is_symlink():
            raise ValueError(f"{repo / rel} 가 심볼릭 링크라 거부한다 — 실제 폴더로 바꾼 뒤 다시 돌린다")
    return repo / ".agents" / "skills" / name, repo / ".claude" / "skills" / name


def expected_target(name):
    return os.path.join("..", "..", ".agents", "skills", name)


def is_placeholder_file(dst, name):
    """Windows 에서 core.symlinks=false 로 클론하면 링크가 대상 경로만 담은 일반 파일이 된다."""
    try:
        text = dst.read_text(encoding="utf-8").strip().replace("\\", "/")
    except (OSError, UnicodeDecodeError):
        return False
    return text == expected_target(name).replace("\\", "/")


def write_manifest(src, dst):
    lines = [f"{h}  {rel}" for rel, h in tree_hashes(src).items()]
    (dst / MANIFEST).write_text("\n".join(lines) + "\n", encoding="utf-8")


def remove_existing(src, dst, name, force):
    """이 스크립트가 만든 것만 지운다. 거부하면 사유를, 지웠거나 없으면 None 을 돌려준다."""
    if dst.is_symlink():
        if dst.resolve() == src.resolve() or force:
            dst.unlink()
            return None
        return f"{dst} 가 다른 곳({os.readlink(dst)})을 가리킨다 — 확인 후 --force"
    if not dst.exists():
        return None
    if dst.is_file():
        if is_placeholder_file(dst, name):
            dst.unlink()
            return None
        return f"{dst} 가 이미 있고 이 스크립트가 만든 것이 아니다"
    if not (dst / MANIFEST).is_file():
        return f"{dst} 가 이미 있고 이 스크립트가 만든 것이 아니다"
    edited = diff_keys(read_manifest(dst), tree_hashes(dst))
    if edited and not force:
        return f"복사본을 직접 고친 흔적({', '.join(edited)}) — 정본에 옮긴 뒤 다시 돌리거나 --force"
    shutil.rmtree(dst)
    return None


def link(repo, name, copy=False, force=False):
    src, dst = paths(repo, name)
    if not (src / "SKILL.md").is_file():
        print(f"정본 없음: {src}/SKILL.md")
        return 1
    dst.parent.mkdir(parents=True, exist_ok=True)
    # 복사는 임시 폴더에 먼저 만들어 두고, 성공한 뒤에만 기존 것을 교체한다
    staged = None
    if copy:
        staged = Path(tempfile.mkdtemp(prefix=f".{name}.", dir=dst.parent))
        shutil.rmtree(staged)
        shutil.copytree(src, staged)
        write_manifest(src, staged)
    reason = remove_existing(src, dst, name, force)
    if reason:
        if staged:
            shutil.rmtree(staged)
        print("덮어쓰지 않음: " + reason)
        return 2
    if not copy:
        try:
            os.symlink(expected_target(name), dst, target_is_directory=True)
            print(f"링크: {dst} -> {os.readlink(dst)}")
            return 0
        except (OSError, NotImplementedError) as e:
            print(f"심볼릭 링크 실패({e.__class__.__name__}) — 복사로 대신한다")
            staged = Path(tempfile.mkdtemp(prefix=f".{name}.", dir=dst.parent))
            shutil.rmtree(staged)
            shutil.copytree(src, staged)
            write_manifest(src, staged)
    os.replace(staged, dst)
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
    if dst.is_file() and is_placeholder_file(dst, name):
        print(f"표류: {dst} 가 링크 대신 경로 문자열 파일이다(git core.symlinks=false) — link 를 돌려 복사로 바꾼다")
        return 1
    if not dst.is_dir():
        print(f"표류: {dst} 없음 — link 를 돌린다")
        return 1
    if not (dst / MANIFEST).is_file():
        print(f"표류: {dst} 에 {MANIFEST} 가 없다 — 이 스크립트가 만든 복사본이 아니다")
        return 1
    recorded, now_src, now_dst = read_manifest(dst), tree_hashes(src), tree_hashes(dst)
    problems = []
    edited = diff_keys(recorded, now_dst)
    if edited:
        problems.append("복사본을 직접 고침 — " + ", ".join(edited))
    changed = diff_keys(recorded, now_src)
    if changed:
        problems.append("정본이 바뀜(link 를 다시 돌린다) — " + ", ".join(changed))
    if problems:
        print("표류: " + " / ".join(problems))
        return 1
    print(f"정상: 복사본 {dst} 가 정본과 같음 (파일 {len(now_src)}개)")
    return 0


def main(argv):
    flags = {a for a in argv if a.startswith("--")}
    args = [a for a in argv if not a.startswith("--")]
    if flags - FLAGS or len(args) != 3 or args[0] not in ("link", "check"):
        print(__doc__)
        return 2
    cmd, repo, name = args
    if not NAME_RE.match(name):
        print("이름은 verify-<앱> 형식의 폴더 이름 하나여야 한다 (예: verify-order-api)")
        return 2
    try:
        if cmd == "link":
            return link(repo, name, "--copy" in flags, "--force" in flags)
        return check(repo, name)
    except ValueError as e:
        print("거부: " + str(e))
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
