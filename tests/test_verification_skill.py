#!/usr/bin/env python3
"""verification-skill link_skill.py 회귀 테스트: 상대 링크, 복사 + sha256 표류 감지, 덮어쓰기 거부."""
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "verification-skill", "scripts", "link_skill.py")
NAME = "verify-order-api"


def can_symlink():
    with tempfile.TemporaryDirectory() as d:
        try:
            os.symlink(d, os.path.join(d, "l"), target_is_directory=True)
            return True
        except (OSError, NotImplementedError):
            return False


SYMLINK = can_symlink()
needs_symlink = unittest.skipUnless(SYMLINK, "이 환경에서 심볼릭 링크를 만들 수 없다")


def load_module():
    spec = importlib.util.spec_from_file_location("link_skill", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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

    @needs_symlink
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

    @needs_symlink
    def test_broken_or_missing(self):
        self.assertEqual(run("check", self.d, NAME).returncode, 1)
        os.makedirs(os.path.dirname(self.dst))
        os.symlink("../../elsewhere", self.dst)
        self.assertEqual(run("check", self.d, NAME).returncode, 1)
        self.assertEqual(run("link", self.d, NAME).returncode, 2)  # 남의 링크는 --force 없이 교체하지 않는다
        self.assertEqual(run("link", self.d, NAME, "--force").returncode, 0)
        self.assertEqual(run("check", self.d, NAME).returncode, 0)

    def test_refuses_to_overwrite_foreign_dir(self):
        write(self.dst, "SKILL.md", "user's own\n")
        r = run("link", self.d, NAME)
        self.assertEqual(r.returncode, 2)
        with open(os.path.join(self.dst, "SKILL.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "user's own\n")

    def test_bad_name_flag_and_missing_source(self):
        for bad in ("../x", "C:verify-x", "/abs", "order-api", "verify-a/b"):
            self.assertEqual(run("link", self.d, bad).returncode, 2, bad)
        self.assertEqual(run("link", self.d, NAME, "--cpy").returncode, 2)
        self.assertFalse(os.path.lexists(self.dst))
        self.assertEqual(run("link", self.d, "verify-none").returncode, 1)

    def test_edited_copy_is_not_silently_replaced(self):
        self.assertEqual(run("link", self.d, NAME, "--copy").returncode, 0)
        write(self.dst, "SKILL.md", "직접 고침\n")
        r = run("check", self.d, NAME)
        self.assertEqual(r.returncode, 1)
        self.assertIn("직접 고침", r.stdout)
        self.assertEqual(run("link", self.d, NAME, "--copy").returncode, 2)
        with open(os.path.join(self.dst, "SKILL.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "직접 고침\n")
        self.assertEqual(run("link", self.d, NAME, "--copy", "--force").returncode, 0)
        self.assertEqual(run("check", self.d, NAME).returncode, 0)

    def test_symlink_failure_falls_back_to_copy(self):
        mod = load_module()
        def fail(*a, **k):
            raise OSError("no symlink privilege")
        orig, mod.os.symlink = mod.os.symlink, fail
        try:
            with unittest.mock.patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(mod.link(self.d, NAME), 0)
        finally:
            mod.os.symlink = orig
        self.assertFalse(os.path.islink(self.dst))
        self.assertTrue(os.path.isfile(os.path.join(self.dst, ".knack-copy.sha256")))
        self.assertEqual(run("check", self.d, NAME).returncode, 0)

    def test_failed_fallback_copy_keeps_existing_copy(self):
        self.assertEqual(run("link", self.d, NAME, "--copy").returncode, 0)
        mod = load_module()
        def fail(*a, **k):
            raise OSError("boom")
        with unittest.mock.patch.object(mod.os, "symlink", fail), \
                unittest.mock.patch.object(mod.shutil, "copytree", fail), \
                unittest.mock.patch("sys.stdout", new=io.StringIO()):
            with self.assertRaises(OSError):
                mod.link(self.d, NAME)
        self.assertEqual(run("check", self.d, NAME).returncode, 0)  # 기존 사본이 그대로 남는다
        leftovers = [n for n in os.listdir(os.path.dirname(self.dst)) if n != NAME]
        self.assertEqual(leftovers, [])

    def test_windows_placeholder_file_is_replaced(self):
        write(os.path.dirname(self.dst), NAME, "../../.agents/skills/" + NAME + "\n")
        r = run("check", self.d, NAME)
        self.assertEqual(r.returncode, 1)
        self.assertIn("core.symlinks", r.stdout)
        self.assertEqual(run("link", self.d, NAME, "--copy").returncode, 0)
        self.assertEqual(run("check", self.d, NAME).returncode, 0)

    @needs_symlink
    def test_refuses_symlinked_parent(self):
        outside = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(outside))
        os.symlink(outside, os.path.join(self.d, ".claude"), target_is_directory=True)
        self.assertEqual(run("link", self.d, NAME, "--copy").returncode, 2)
        self.assertEqual(os.listdir(outside), [])


class Templates(unittest.TestCase):
    def test_generated_skill_template_has_sections_and_unproven_state(self):
        with open(os.path.join(ROOT, "skills", "verification-skill", "templates", "verify-SKILL.md"), encoding="utf-8") as f:
            s = f.read()
        self.assertTrue(s.startswith("---\nname: verify-"))
        for h in ("## 띄우기", "## 점검", "## 조작", "## 증거", "## 정리", "**미증명**"):
            self.assertIn(h, s)


if __name__ == "__main__":
    unittest.main()
