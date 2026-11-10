#!/usr/bin/env python3
"""MCP 자동 로그인 훅: 허용 목록·비대화 건너뜀·시간 한도·fail-open 을 확인한다."""
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hooks" / "_shared"))
import mcp_login  # noqa: E402


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


codex_hook = load("codex_hook", "hooks/mcp-auto-login/hook.py")
claude_hook = load("claude_hook", "hooks/mcp-auto-login-claude/hook.py")
OK = subprocess.CompletedProcess([], 0)
INTERACTIVE = lambda: ["/opt/bin/codex", "/bin/zsh -l"]  # noqa: E731


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = Path(self.tmp.name) / "mcp-auto-login.local.json"
        patcher = patch.object(mcp_login, "CONFIG", self.config)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def allow(self, **agents):
        self.config.write_text(json.dumps({a: {"servers": s} for a, s in agents.items()}), encoding="utf-8")

    def run_logins(self, agent, pending, **kwargs):
        calls, out = [], io.StringIO()

        def fake(cmd, **kw):
            calls.append((cmd, kw.get("timeout")))
            return kwargs.get("result", OK)

        with redirect_stdout(out):
            mcp_login.run(agent, pending, [agent, "mcp", "login"], run_cmd=kwargs.get("run_cmd", fake),
                          clock=kwargs.get("clock", lambda: 0.0))
        return calls, out.getvalue()


class Allowlist(Base):
    def test_without_config_nothing_is_allowed(self):
        self.assertEqual(mcp_login.allowed("codex"), set())
        self.assertEqual(self.run_logins("codex", ["atlassian"])[0], [])

    def test_only_listed_servers_for_that_agent(self):
        self.allow(codex=["atlassian"], claude=["docs"])
        calls, _ = self.run_logins("codex", ["atlassian", "evil-from-repo", "docs"])
        self.assertEqual([c[0] for c in calls], [["codex", "mcp", "login", "atlassian"]])

    def test_bad_config_and_option_like_names_are_ignored(self):
        self.config.write_text("{not json", encoding="utf-8")
        self.assertEqual(mcp_login.allowed("codex"), set())
        self.config.write_text(json.dumps({"codex": {"servers": "atlassian"}}), encoding="utf-8")
        self.assertEqual(mcp_login.allowed("codex"), set())
        self.allow(codex=["--no-browser", "ok", 3])
        self.assertEqual(mcp_login.allowed("codex"), {"ok"})


class Attended(unittest.TestCase):
    def check(self, agent, data=None, env=None, chain=INTERACTIVE):
        return mcp_login.attended(agent, data or {}, env=env or {}, commands=chain)[0]

    def test_interactive_new_session(self):
        self.assertTrue(self.check("codex"))
        self.assertTrue(self.check("claude", {"source": "startup"}, chain=lambda: ["/x/claude --model opus"]))

    def test_resume_clear_compact_are_skipped(self):
        for source in ("resume", "clear", "compact"):
            self.assertFalse(self.check("claude", {"source": source}))

    def test_ci_ssh_and_sdk_are_skipped(self):
        self.assertFalse(self.check("codex", env={"CI": "true"}))
        self.assertFalse(self.check("codex", env={"SSH_CONNECTION": "1.2.3.4 1 5.6.7.8 22"}))
        self.assertFalse(self.check("claude", env={"CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}))

    def test_headless_invocations_are_skipped(self):
        self.assertFalse(self.check("codex", chain=lambda: ["/opt/bin/codex exec -s read-only -"]))
        self.assertFalse(self.check("claude", chain=lambda: ["/x/claude --model sonnet --print"]))
        self.assertFalse(self.check("claude", chain=lambda: ["node hook-runner", "/x/claude -p hi"]))

    def test_unknown_parent_is_skipped(self):
        self.assertFalse(self.check("codex", chain=lambda: None))


class Run(Base):
    def test_failure_is_reported_by_name_only(self):
        self.allow(codex=["atlassian"])
        _, out = self.run_logins("codex", ["atlassian"], result=subprocess.CompletedProcess([], 1))
        self.assertIn("atlassian", json.loads(out)["hookSpecificOutput"]["additionalContext"])

    def test_total_time_is_bounded(self):
        self.allow(codex=["a", "b", "c"])
        now = [0.0]

        def slow(cmd, **kw):
            now[0] += kw["timeout"]
            raise subprocess.TimeoutExpired(cmd, kw["timeout"])

        calls = []
        _, out = self.run_logins("codex", ["a", "b", "c"], clock=lambda: now[0],
                                 run_cmd=lambda cmd, **kw: (calls.append(kw["timeout"]), slow(cmd, **kw))[1])
        self.assertEqual(calls, [100, 10])
        self.assertLessEqual(now[0], mcp_login.BUDGET)
        text = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("시간 한도로 건너뜀: c", text)

    def test_second_session_does_not_wait_for_the_lock(self):
        self.allow(codex=["a"])
        import fcntl
        path = os.path.join(tempfile.gettempdir(), f"knack-mcp-login-codex-{os.getuid()}.lock")
        with open(path, "a") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            calls, out = self.run_logins("codex", ["a"])
        self.assertEqual(calls, [])
        self.assertIn("진행 중", out)


class Parsing(unittest.TestCase):
    def test_codex_picks_enabled_remote_logged_out(self):
        servers = [
            {"name": "pending", "enabled": True, "auth_status": "not_logged_in", "transport": {"type": "streamable_http"}},
            {"name": "ready", "enabled": True, "auth_status": "o_auth", "transport": {"type": "sse"}},
            {"name": "local", "enabled": True, "auth_status": "not_logged_in", "transport": {"type": "stdio"}},
            {"name": "off", "enabled": False, "auth_status": "not_logged_in", "transport": {"type": "sse"}},
            {"enabled": True, "auth_status": "not_logged_in", "transport": {"type": "sse"}},
            "garbage",
        ]
        self.assertEqual(codex_hook.pending_servers(json.dumps(servers)), ["pending"])

    def test_codex_unexpected_shape_is_not_a_crash(self):
        self.assertIsNone(codex_hook.pending_servers("not json"))
        self.assertIsNone(codex_hook.pending_servers('{"servers": []}'))

    def test_claude_picks_only_needs_authentication(self):
        output = ("Checking MCP server health…\n"
                  "atlassian: https://example.test/mcp - ✘ Needs authentication\n"
                  "plugin:team:docs: https://example.test - ✘ Needs authentication\n"
                  "ready: https://example.test - ✓ Connected\n"
                  "local: /bin/tool - ✘ Failed to connect\n"
                  "pending: https://example.test - ⏸ Pending approval\n")
        self.assertEqual(claude_hook.pending_servers(output), ["atlassian", "plugin:team:docs"])


class EndToEnd(unittest.TestCase):
    def hook(self, rel, stdin, env=None):
        e = {k: v for k, v in os.environ.items() if k not in ("CI", "SSH_CONNECTION", "SSH_TTY")}
        e.update(env or {})
        return subprocess.run([sys.executable, str(ROOT / rel)], input=stdin, capture_output=True, text=True, env=e)

    def test_no_config_exits_quietly_without_calling_the_cli(self):
        with tempfile.TemporaryDirectory() as d:
            marker = Path(d) / "called"
            for name in ("codex", "claude"):
                (Path(d) / name).write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
                (Path(d) / name).chmod(0o755)
            env = {"PATH": d + os.pathsep + os.environ["PATH"], "KNACK_MCP_LOGIN_CONFIG": str(Path(d) / "none.json")}
            for rel in ("hooks/mcp-auto-login/hook.py", "hooks/mcp-auto-login-claude/hook.py"):
                for stdin in ('{"source":"startup"}', "not json", ""):
                    p = self.hook(rel, stdin, env)
                    self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))
            self.assertFalse(marker.exists())

    def test_headless_parent_never_logs_in_even_when_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            marker, config = Path(d) / "called", Path(d) / "c.json"
            config.write_text(json.dumps({"codex": {"servers": ["a"]}}), encoding="utf-8")
            (Path(d) / "codex").write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
            (Path(d) / "codex").chmod(0o755)
            p = self.hook("hooks/mcp-auto-login/hook.py", "{}",
                          {"PATH": d + os.pathsep + os.environ["PATH"], "KNACK_MCP_LOGIN_CONFIG": str(config), "CI": "1"})
            self.assertEqual((p.returncode, p.stdout), (0, ""))
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
