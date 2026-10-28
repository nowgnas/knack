import argparse
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
import knack as k


class ModelSyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cfg = k.load_models(merge=False)
        self.role = next(g for g in k.knack_agents() if g['name'] == 'verifier')
        for name, value in {
            'CODEX_CONFIG': self.root / 'config.toml',
            'CODEX_ROLE_DIR': self.root / 'roles',
            'OLD_CODEX_ROLE_DIR': self.root / 'old',
            '_CODEX_MODELS': {'available-model': ['low']},
        }.items():
            p = patch.object(k, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(k, 'load_models', return_value=self.cfg)
        p.start()
        self.addCleanup(p.stop)
        k.CODEX_CONFIG.write_text('model = "available-model"\nmodel_reasoning_effort = "low"\n')

    def sync(self):
        args = argparse.Namespace(action='install', agent='codex', no_main=False,
                                  dry_run=False, backup_dir=str(self.root / 'backup'))
        with contextlib.redirect_stdout(io.StringIO()):
            k.cmd_models_sync(args)
        return k.CODEX_CONFIG.read_text()

    def doctor(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            k.cmd_doctor(None)
        return output.getvalue()

    def test_missing_candidates_preserve_default_and_omit_role_override(self):
        self.cfg['main']['codex'] = {'model': ['gone-model'], 'effort': 'high'}
        self.cfg['tiers']['codex']['standard'] = {'model': ['gone-model'], 'effort': 'high'}
        text = self.sync()
        self.assertEqual(k.toml_top(text, 'model'), 'available-model')
        self.assertEqual(k.toml_top(text, 'model_reasoning_effort'), 'low')
        role = k.render_codex_role(self.role, self.cfg)
        self.assertNotIn('\nmodel =', role)
        self.assertNotIn('\nmodel_reasoning_effort =', role)
        self.assertEqual(self.sync(), text)

    def test_unsupported_effort_removed_without_changing_nested_config(self):
        self.cfg['main']['codex'] = {'model': ['gone-model', 'available-model'], 'effort': 'high'}
        k.CODEX_CONFIG.write_text('model = "old"\nmodel_reasoning_effort = "high"\n[profiles.custom]\nmodel_reasoning_effort = "high"\n')
        text = self.sync()
        self.assertEqual(k.toml_top(text, 'model'), 'available-model')
        self.assertIsNone(k.toml_top(text, 'model_reasoning_effort'))
        self.assertIn('[profiles.custom]\nmodel_reasoning_effort = "high"', text)
        self.assertEqual(self.sync(), text)

    def test_doctor_detects_role_block_and_main_drift(self):
        self.cfg['main']['codex'] = {'model': 'available-model', 'effort': 'low'}
        self.sync()
        clean = self.doctor()
        self.assertNotIn('codex:역할 블록', clean)
        self.assertNotIn('codex:기본 모델', clean)
        text = k.CODEX_CONFIG.read_text().replace('model = "available-model"', 'model = "old"', 1)
        text = text.replace('description = ', 'description = "changed" # ', 1)
        k.CODEX_CONFIG.write_text(text)
        output = self.doctor()
        self.assertIn('codex:역할 블록', output)
        self.assertIn('codex:기본 모델', output)


if __name__ == '__main__':
    unittest.main()
