#!/usr/bin/env python3
"""verification-skill link_skill.py 회귀 테스트: 상대 링크, 복사 + sha256 표류 감지, 덮어쓰기 거부."""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "verification-skill", "scripts", "link_skill.py")
NAME = "verify-order-api"


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)


def write(base, rel, text):
    p = os.path.join(base, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


class LinkSkill(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.src = os.path.join(self.d, ".agents", "skills", NAME)
        self.dst = os.path.join(self.d, ".claude", "skills", NAME)
        write(self.src, "SKILL.md", "---\nname: verify-order-api\n---\n")
        write(self.src, "features/README.md", "- orders\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_relative_symlink_and_check(self):
        r = run("link", self.d, NAME)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(os.path.islink(self.dst))
        self.assertEqual(os.readlink(self.dst), os.path.join("..", "..", ".agents", "skills", NAME))
        self.assertEqual(run("check", self.d, NAME).returncode, 0)

    def test_copy_detects_drift(self):
        self.assertEqual(run("link", self.d, NAME, "--copy").returncode, 0)
        self.assertFalse(os.path.islink(self.dst))
        self.assertTrue(os.path.isfile(os.path.join(self.dst, ".knack-copy.sha256")))
        self.assertEqual(run("check", self.d, NAME).returncode, 0)
        write(self.src, "features/orders.md", "# 주문\n")
        r = run("check", self.d, NAME)
        self.assertEqual(r.returncode, 1)
        self.assertIn("features/orders.md", r.stdout)
        self.assertEqual(run("link", self.d, NAME, "--copy").returncode, 0)
        self.assertEqual(run("check", self.d, NAME).returncode, 0)

    def test_broken_or_missing(self):
        self.assertEqual(run("check", self.d, NAME).returncode, 1)
        os.makedirs(os.path.dirname(self.dst))
        os.symlink("../../elsewhere", self.dst)
        self.assertEqual(run("check", self.d, NAME).returncode, 1)
        self.assertEqual(run("link", self.d, NAME).returncode, 0)
        self.assertEqual(run("check", self.d, NAME).returncode, 0)

    def test_refuses_to_overwrite_foreign_dir(self):
        write(self.dst, "SKILL.md", "user's own\n")
        r = run("link", self.d, NAME)
        self.assertEqual(r.returncode, 2)
        with open(os.path.join(self.dst, "SKILL.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "user's own\n")

    def test_bad_name_and_missing_source(self):
        self.assertEqual(run("link", self.d, "../x").returncode, 2)
        self.assertEqual(run("link", self.d, "verify-none").returncode, 1)


class Templates(unittest.TestCase):
    def test_generated_skill_template_has_sections_and_unproven_state(self):
        with open(os.path.join(ROOT, "skills", "verification-skill", "templates", "verify-SKILL.md"), encoding="utf-8") as f:
            s = f.read()
        self.assertTrue(s.startswith("---\nname: verify-"))
        for h in ("## 띄우기", "## 점검", "## 조작", "## 증거", "## 정리", "**미증명**"):
            self.assertIn(h, s)


if __name__ == "__main__":
    unittest.main()
