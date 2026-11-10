import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'hooks/mcp-auto-login/hook.py'
spec = importlib.util.spec_from_file_location('mcp_auto_login', path)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class AutoLoginTest(unittest.TestCase):
    def test_other_machine_does_not_run_commands(self):
        with patch.object(hook.platform, 'system', return_value='Darwin'), patch.object(hook.platform, 'node', return_value='other'), patch.object(hook.subprocess, 'run') as run:
            hook.main()
            run.assert_not_called()

    def test_only_enabled_remote_logged_out_servers_are_authenticated(self):
        servers = [
            {'name': 'pending', 'enabled': True, 'auth_status': 'not_logged_in', 'transport': {'type': 'streamable_http'}},
            {'name': 'ready', 'enabled': True, 'auth_status': 'o_auth', 'transport': {'type': 'streamable_http'}},
            {'name': 'local', 'enabled': True, 'auth_status': 'unsupported', 'transport': {'type': 'stdio'}},
            {'name': 'disabled', 'enabled': False, 'auth_status': 'not_logged_in', 'transport': {'type': 'streamable_http'}},
        ]
        responses = [subprocess.CompletedProcess([], 0, stdout=json.dumps(servers)), subprocess.CompletedProcess([], 0)]
        with patch.object(hook.platform, 'system', return_value='Darwin'), patch.object(hook.platform, 'node', return_value='YPK7M177JY.local'), patch.object(hook.getpass, 'getuser', return_value='sangwolee'), patch.object(hook.subprocess, 'run', side_effect=responses) as run:
            hook.main()
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[1].args[0], ['codex', 'mcp', 'login', 'pending'])

    def test_failed_login_is_reported_without_credentials(self):
        servers = [{'name': 'pending', 'enabled': True, 'auth_status': 'not_logged_in', 'transport': {'type': 'sse'}}]
        responses = [subprocess.CompletedProcess([], 0, stdout=json.dumps(servers)), subprocess.CompletedProcess([], 1)]
        with patch.object(hook.platform, 'system', return_value='Darwin'), patch.object(hook.platform, 'node', return_value='YPK7M177JY'), patch.object(hook.getpass, 'getuser', return_value='sangwolee'), patch.object(hook.subprocess, 'run', side_effect=responses), patch.object(hook, 'notify') as notify:
            hook.main()
        self.assertIn('pending', notify.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
