import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'hooks/mcp-auto-login-claude/hook.py'
spec = importlib.util.spec_from_file_location('claude_auto_login', path)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class AutoLoginTest(unittest.TestCase):
    def test_parse_only_authentication_needed(self):
        output = ('Checking MCP server health…\n'
                  'atlassian: https://example.test/mcp - ✘ Needs authentication\n'
                  'plugin:team:docs: https://example.test - ✘ Needs authentication\n'
                  'ready: https://example.test - ✓ Connected\n'
                  'local: /bin/tool - ✘ Failed to connect\n'
                  'pending: https://example.test - ⏸ Pending approval\n')
        self.assertEqual(hook.pending_servers(output), ['atlassian', 'plugin:team:docs'])

    def test_other_device_does_not_run(self):
        with patch.object(hook.platform, 'system', return_value='Darwin'), patch.object(hook.platform, 'node', return_value='other'), patch.object(hook.subprocess, 'run') as run:
            hook.main()
            run.assert_not_called()

    def test_authenticates_only_required_server(self):
        responses = [subprocess.CompletedProcess([], 0, stdout='docs: https://example.test - ✘ Needs authentication\nlocal: /bin/tool - ✘ Failed to connect'), subprocess.CompletedProcess([], 0)]
        with patch.object(hook.platform, 'system', return_value='Darwin'), patch.object(hook.platform, 'node', return_value='YPK7M177JY.local'), patch.object(hook.getpass, 'getuser', return_value='sangwolee'), patch.object(hook.subprocess, 'run', side_effect=responses) as run:
            hook.main()
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[1].args[0], ['claude', 'mcp', 'login', 'docs'])


if __name__ == '__main__':
    unittest.main()
