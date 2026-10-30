#!/usr/bin/env python3
"""mistake-proofing mistakes.py 회귀 테스트: 커밋되는 원장(docs/mistakes.md) 집계, 2회 판정, enforcement.md 대조, 새 clone."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "mistake-proofing", "scripts", "mistakes.py")


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)


def write(base, rel, text):
    p = os.path.join(base, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


HEAD = "| 날짜 | 태그 | 한 줄 요약 | 버그 기록 |\n|---|---|---|---|\n"


def row(slug, record="-", date="2026-10-30", note="요약"):
    return f"| {date} | `mistake:{slug}` | {note} | {record} |\n"


class Mistakes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def ledger(self, *rows, head=HEAD):
        write(self.d, "docs/mistakes.md", head + "".join(rows))

    def test_single_occurrence_passes(self):
        self.ledger(row("missing-tx", "#12"))
        self.assertEqual(run("check", self.d).returncode, 0)
        self.assertIn("1회", run("list", self.d).stdout)

    def test_repeat_without_enforcement_fails_then_passes(self):
        self.ledger(row("missing-tx", "#12"), row("Missing-Tx", "#30"))  # 대소문자는 같은 태그
        r = run("check", self.d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("mistake:missing-tx (2회", r.stdout)
        write(self.d, "docs/enforcement.md", "| `mistake:missing-tx` | 룰 | ArchUnit | cmd | 증명 |\n")
        self.assertEqual(run("check", self.d).returncode, 0)
        self.assertIn("증명됨", run("list", self.d).stdout)

    def test_same_bug_twice_counts_once_but_no_record_counts_each(self):
        self.ledger(row("missing-tx", "#12"), row("missing-tx", "#12"))
        self.assertEqual(run("check", self.d).returncode, 0)
        self.ledger(row("missing-tx"), row("missing-tx", "—"))  # 기록 없는 행은 각각 센다
        self.assertEqual(run("check", self.d).returncode, 1)

    def test_bugfix_files_and_prose_are_not_counted(self):
        write(self.d, ".design/bug-a/BUGFIX.md", "실수 태그: mistake:missing-tx\n")
        write(self.d, ".design/bug-b/BUGFIX.md", "실수 태그: mistake:missing-tx\n")
        self.ledger("설명 속 mistake:missing-tx 언급\n", head=HEAD + "| `mistake:<slug>` 자리표시자 | | | |\n")
        self.assertEqual(run("check", self.d).returncode, 0)

    def test_template_ledger_is_valid_and_empty(self):
        with open(os.path.join(ROOT, "skills", "mistake-proofing", "templates", "mistakes.md"), encoding="utf-8") as f:
            write(self.d, "docs/mistakes.md", f.read())
        r = run("list", self.d)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("기록 없음", r.stdout)

    def test_malformed_ledger_rows_exit_2(self):
        for bad in ("| 2026-10-30 | `mistake:a` | 요약 |\n",                      # 열 부족
                    "| 2026-10-30 | `mistake:a` | a | b | c |\n",                # 이스케이프 안 된 |
                    "| 2026-10-30 | `mistake:a` `mistake:b` | 요약 | - |\n",       # 태그 두 개
                    "| 어제 | `mistake:a` | 요약 | - |\n",                         # 날짜 형식
                    "| 2026-13-45 | `mistake:a` | 요약 | - |\n",                   # 없는 날짜
                    "| `mistake:a` | 2026-10-30 | 요약 | - |\n",                   # 열 순서가 바뀜
                    "| 2026-10-30 | 요약 | `mistake:a` | - |\n",                   # 태그를 요약 칸에
                    "| 2026-10-30 | `mistake:missing_tx` | 요약 | - |\n",          # 태그 오타
                    "| 2026-10-30 |  | 요약 | - |\n"):                             # 빈 태그
            self.ledger(bad)
            r = run("check", self.d)
            self.assertEqual(r.returncode, 2, bad)
            self.assertIn("docs/mistakes.md:3", r.stdout)
        self.ledger("| 2026-10-30 | `mistake:a` | `x \\| y` 누락 | - |\n")
        self.assertEqual(run("check", self.d).returncode, 0)  # 칸 안의 \| 는 구분자가 아니다

    def test_code_block_rows_are_not_counted(self):
        self.ledger(row("a", "#1"), "\n```\n" + row("a", "#2") + "```\n")
        self.assertIn("mistake:a\t1회", run("list", self.d).stdout)

    def test_broken_docs_link_exit_2(self):
        os.symlink(os.path.join(self.d, "nowhere"), os.path.join(self.d, "docs"))
        self.assertEqual(run("check", self.d).returncode, 2)

    @unittest.skipUnless(shutil.which("git"), "git 없음")
    def test_fresh_clone_counts_like_ci(self):
        """bug-fix 방식(.design 은 gitignore, 원장은 커밋)으로 만든 레포를 새로 clone 해도 재발을 잡는다."""
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main"]
        src = os.path.join(self.d, "src")
        os.makedirs(src)
        write(src, ".design/.gitignore", "*\n")
        write(src, ".design/bug-a/BUGFIX.md", "실수 태그: mistake:missing-tx\n")
        write(src, "docs/mistakes.md", HEAD + row("missing-tx", "#12") + row("missing-tx", "#30"))
        for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "init"]):
            subprocess.run(git + cmd, cwd=src, check=True, capture_output=True)
        clone = os.path.join(self.d, "clone")
        subprocess.run(git + ["clone", "-q", src, clone], check=True, capture_output=True)
        self.assertFalse(os.path.exists(os.path.join(clone, ".design")))
        r = run("list", clone)
        self.assertIn("mistake:missing-tx\t2회", r.stdout)
        self.assertEqual(run("check", clone).returncode, 1)

    def test_mention_or_incomplete_row_is_not_enforcement(self):
        self.ledger(row("missing-tx", "#1"), row("missing-tx", "#2"))
        cases = [
            "설명 문장 속 mistake:missing-tx 언급\n",
            "| `mistake:missing-tx` | 룰 | ArchUnit | cmd | 미증명 |\n",
            "| `mistake:missing-tx` | 룰 | ArchUnit | cmd | |\n",
            "| `mistake:missing-tx` | <한 문장 룰> | ArchUnit | cmd | 증명 |\n",
            "| `mistake:missing-tx` | 룰 | 강제 불가 | | |\n",              # 사유 없는 강제 불가
            "| `mistake:missing-tx` | 룰 | 강제 불가 — <사유> | | |\n",
            "| `mistake:missing-tx` | 룰 | 강제 불가 — `<사유>` | | |\n",
            "| `mistake:missing-tx` | 룰 | CI | a | b | |\n",            # 이스케이프 안 된 | 로 열이 밀림
        ]
        for doc in cases:
            write(self.d, "docs/enforcement.md", doc)
            self.assertEqual(run("check", self.d).returncode, 1, doc)
        write(self.d, "docs/enforcement.md", "| `mistake:missing-tx` | 룰 | 강제 불가 — 설계 판단 | - | - |\n")
        self.assertEqual(run("check", self.d).returncode, 0)
        write(self.d, "docs/enforcement.md", "| `mistake:missing-tx` | 룰 | CI | `a \\| b` | exit 1 → 0 |\n")
        self.assertEqual(run("check", self.d).returncode, 0)  # 칸 안의 \| 는 구분자가 아니다

    def test_encodings(self):
        p = os.path.join(self.d, "docs", "mistakes.md")
        os.makedirs(os.path.dirname(p))
        with open(p, "wb") as f:
            f.write((HEAD + row("enc", "#1") + row("enc", "#2")).encode("utf-16"))
        r = run("check", self.d)
        self.assertEqual(r.returncode, 1, r.stdout)  # UTF-16 원장도 센다
        write(self.d, "docs/mistakes.md", "\ufeff" + HEAD + row("enc", "#1"))
        self.assertEqual(run("check", self.d).returncode, 0)
        with open(p, "wb") as f:
            f.write(b"| 2026-10-30 | mistake:enc \xff\xfa | x | - |")  # 잘못된 UTF-8 은 숨기지 않고 exit 2
        self.assertEqual(run("check", self.d).returncode, 2)

    def test_tag_boundaries_and_korean_particle(self):
        self.ledger(row("abc", "#1"), "| 2026-10-30 | nomistake:abc `mistake:abcd` | x | #2 |\n")
        self.assertEqual(run("check", self.d).returncode, 0)  # 다른 태그
        write(self.d, "docs/enforcement.md", "mistake:abcd-more\n")      # 접두어 일치는 강제가 아니다
        self.ledger(row("abcd", "#1"), "| 2026-10-30 | mistake:abcd가 또 | x | #2 |\n")
        self.assertEqual(run("check", self.d).returncode, 1)

    def test_unreadable_ledger(self):
        os.makedirs(os.path.join(self.d, "docs"))
        os.symlink(os.path.join(self.d, "nowhere"), os.path.join(self.d, "docs", "mistakes.md"))
        self.assertEqual(run("check", self.d).returncode, 2)  # 깨진 링크를 "기록 없음"으로 숨기지 않는다
        os.remove(os.path.join(self.d, "docs", "mistakes.md"))
        os.makedirs(os.path.join(self.d, "docs", "mistakes.md"))  # 폴더는 원장이 아니다
        self.assertEqual(run("check", self.d).returncode, 2)

    def test_usage_errors(self):
        self.assertEqual(run("check").returncode, 2)
        self.assertEqual(run("nope", self.d).returncode, 2)
        self.assertEqual(run("check", os.path.join(self.d, "없음")).returncode, 2)


class Templates(unittest.TestCase):
    def test_bugfix_template_has_tag_line(self):
        with open(os.path.join(ROOT, "skills", "bug-fix", "templates", "BUGFIX.md"), encoding="utf-8") as f:
            self.assertIn("mistake:<slug>", f.read())

    def test_ledger_template_columns(self):
        with open(os.path.join(ROOT, "skills", "mistake-proofing", "templates", "mistakes.md"), encoding="utf-8") as f:
            s = f.read()
        for col in ("날짜", "태그", "한 줄 요약", "버그 기록"):
            self.assertIn(col, s)

    def test_enforcement_template_columns(self):
        with open(os.path.join(ROOT, "skills", "mistake-proofing", "templates", "enforcement.md"), encoding="utf-8") as f:
            s = f.read()
        for col in ("태그", "룰", "강제 수단", "실행 명령", "과거 실패 증명"):
            self.assertIn(col, s)


if __name__ == "__main__":
    unittest.main()
