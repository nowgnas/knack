#!/usr/bin/env python3
"""mistake-proofing mistakes.py 회귀 테스트: 태그 수집, 2회 판정, enforcement.md 대조."""
import os
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


class Mistakes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_single_occurrence_passes(self):
        write(self.d, ".design/bug-a/BUGFIX.md", "실수 태그: mistake:missing-tx\n")
        self.assertEqual(run("check", self.d).returncode, 0)
        self.assertIn("1회", run("list", self.d).stdout)

    def test_repeat_without_enforcement_fails_then_passes(self):
        write(self.d, ".design/bug-a/BUGFIX.md", "실수 태그: mistake:missing-tx\n")
        write(self.d, ".design/bug-b/BUGFIX.md", "mistake:missing-tx 와 mistake:missing-tx (같은 파일 중복)\n")
        r = run("check", self.d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("mistake:missing-tx (2회", r.stdout)
        write(self.d, "docs/enforcement.md", "| `mistake:missing-tx` | 룰 | ArchUnit | cmd | 증명 |\n")
        self.assertEqual(run("check", self.d).returncode, 0)
        self.assertIn("강제됨", run("list", self.d).stdout)

    def test_tag_boundaries_and_skipped_dirs(self):
        write(self.d, ".design/bug-a/BUGFIX.md", "mistake:abc\n")
        write(self.d, "build/x/BUGFIX.md", "mistake:abc\n")            # 빌드 산출물은 세지 않는다
        write(self.d, ".design/bug-b/BUGFIX.md", "nomistake:abc mistake:abcd\n")  # 다른 태그
        self.assertEqual(run("check", self.d).returncode, 0)
        write(self.d, "docs/enforcement.md", "mistake:abcd-more\n")      # 접두어 일치는 강제가 아니다
        write(self.d, ".design/bug-c/BUGFIX.md", "mistake:abcd\n")
        self.assertEqual(run("check", self.d).returncode, 1)

    def test_usage_errors(self):
        self.assertEqual(run("check").returncode, 2)
        self.assertEqual(run("nope", self.d).returncode, 2)
        self.assertEqual(run("check", os.path.join(self.d, "없음")).returncode, 2)


class Templates(unittest.TestCase):
    def test_bugfix_template_has_tag_line(self):
        with open(os.path.join(ROOT, "skills", "bug-fix", "templates", "BUGFIX.md"), encoding="utf-8") as f:
            self.assertIn("mistake:<slug>", f.read())

    def test_enforcement_template_columns(self):
        with open(os.path.join(ROOT, "skills", "mistake-proofing", "templates", "enforcement.md"), encoding="utf-8") as f:
            s = f.read()
        for col in ("태그", "룰", "강제 수단", "실행 명령", "과거 실패 증명"):
            self.assertIn(col, s)


if __name__ == "__main__":
    unittest.main()
