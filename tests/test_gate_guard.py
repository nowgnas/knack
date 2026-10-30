#!/usr/bin/env python3
"""knack gate 의 CHECK 사전 검사(guard_denies): 꺼짐은 hook.json enabled=false 만, 판단할 수 없으면 막는다."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))
import gate  # noqa: E402

REAL = gate.GUARD_PROD
MIGRATE = "flyway migrate"
LOCAL = "flyway -url=jdbc:postgresql://localhost:5432/app migrate"


class FakeHook(unittest.TestCase):
    """가짜 훅 폴더로 실패 경로를 본다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        gate.GUARD_PROD = self.dir
        self.spec({"enabled": True})

    def tearDown(self):
        gate.GUARD_PROD = REAL
        self.tmp.cleanup()

    def spec(self, value):
        (self.dir / "hook.json").write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")

    def hook(self, body):
        (self.dir / "guard_prod.py").write_text("import sys\n" + body + "\n", encoding="utf-8")

    def check(self):
        return gate.guard_denies("echo hi", self.dir)

    def test_disabled_skips(self):
        self.spec({"enabled": False})
        self.hook("print('garbage'); sys.exit(3)")
        self.assertIsNone(self.check())

    def test_bad_config_denies(self):
        self.hook("")
        for bad in ('{"enabled": null}', '{"enabled": 0}', '[]', 'null', '{'):
            self.spec(bad)
            self.assertIsNotNone(self.check(), bad)
        (self.dir / "hook.json").unlink()
        self.assertIsNotNone(self.check())

    def test_empty_output_exit_0_allows(self):
        self.hook("")
        self.assertIsNone(self.check())

    def test_unjudgeable_output_denies(self):
        for body in ("sys.exit(1)", "raise SystemExit('boom')", "print('garbage')", "print('{}')",
                     "print('{\"hookSpecificOutput\": {}}')", "print('{\"hookSpecificOutput\": null}')",
                     "print('{\"hookSpecificOutput\": {\"permissionDecision\": \"ask\"}}')"):
            self.hook(body)
            self.assertIsNotNone(self.check(), body)
        (self.dir / "guard_prod.py").unlink()
        self.assertIsNotNone(self.check())

    def test_deny_reason_and_allow(self):
        self.hook("print('{\"hookSpecificOutput\": {\"permissionDecision\": \"deny\", \"permissionDecisionReason\": \"운영\"}}')")
        self.assertEqual(self.check(), "운영")
        self.hook("print('{\"hookSpecificOutput\": {\"permissionDecision\": \"allow\"}}')")
        self.assertIsNotNone(self.check())  # 허용은 exit 0 + 빈 출력뿐

    def test_timeout_denies(self):
        old, gate.GUARD_TIMEOUT = gate.GUARD_TIMEOUT, 1
        try:
            self.hook("import time; time.sleep(5)")
            self.assertIsNotNone(self.check())
        finally:
            gate.GUARD_TIMEOUT = old


def real_enabled():
    try:
        return json.loads((REAL / "hook.json").read_text(encoding="utf-8")).get("enabled", True) is True
    except (OSError, ValueError, AttributeError):
        return False


class RealHook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("KNACK_GUARD_PROD")

    def tearDown(self):
        if self.old is None:
            os.environ.pop("KNACK_GUARD_PROD", None)
        else:
            os.environ["KNACK_GUARD_PROD"] = self.old
        self.tmp.cleanup()

    @unittest.skipUnless(real_enabled(), "이 PC 에서 guard-prod-ops 가 꺼져 있음")
    def test_migration_without_target_denied_local_allowed(self):
        self.assertIsNotNone(gate.guard_denies(MIGRATE, self.tmp.name))
        self.assertIsNone(gate.guard_denies(LOCAL, self.tmp.name))

    @unittest.skipUnless(real_enabled(), "이 PC 에서 guard-prod-ops 가 꺼져 있음")
    def test_env_off_does_not_bypass(self):
        os.environ["KNACK_GUARD_PROD"] = "off"
        import subprocess
        payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                              "tool_input": {"command": MIGRATE}, "cwd": self.tmp.name})
        direct = subprocess.run([sys.executable, str(REAL / "guard_prod.py")], input=payload.encode(), capture_output=True)
        self.assertEqual(direct.stdout.strip(), b"")  # 대조: 훅만 부르면 off 로 건너뛴다
        self.assertIsNotNone(gate.guard_denies(MIGRATE, self.tmp.name))


if __name__ == "__main__":
    unittest.main()
