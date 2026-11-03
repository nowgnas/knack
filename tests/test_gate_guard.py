#!/usr/bin/env python3
"""gate CHECK가 하네스 훅의 명령 내용 검사 없이 실행되는지 확인한다."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))
import gate  # noqa: E402


class GateExecution(unittest.TestCase):
    def test_check_runs_without_guard_inspection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "flyway").write_text("#!/bin/sh\nprintf migrated > ran.flag\n", encoding="utf-8")
            (root / "flyway").chmod(0o755)
            item = gate.Gate("G1", "local fake", False, 0)
            item.attrs = {"CHECK": "./flyway migrate && cat ran.flag", "EXPECT": "migrated"}
            with patch.object(gate, "GUARD_PROD", root, create=True):
                passed, detail, output = gate.run_gate(item, root, 5)
            self.assertTrue(passed, (detail, output))
            self.assertEqual((root / "ran.flag").read_text(), "migrated")


if __name__ == "__main__":
    unittest.main()
