#!/usr/bin/env python3
"""knack work: 과제 문서 위치가 worktree 사이에서 같고, 진행 기록이 덧붙기만 하는지 확인한다."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNACK = [sys.executable, str(ROOT / "lib" / "knack.py")]
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}


def run(cwd, *args, agent="claude", env=None):
    e = dict(os.environ, KNACK_AGENT=agent, **GIT_ENV)
    e.pop("KNACK_WORK_DIR", None)
    e.update(env or {})
    return subprocess.run([*KNACK, *args], cwd=cwd, env=e, capture_output=True, text=True)


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                   env=dict(os.environ, **GIT_ENV))


class Work(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.main, self.wt = base / "main", base / "wt"
        self.main.mkdir()
        git(self.main, "init", "-q")
        git(self.main, "commit", "-q", "--allow-empty", "-m", "init")
        git(self.main, "worktree", "add", "-q", str(self.wt), "-b", "feat/x")

    def tearDown(self):
        self.tmp.cleanup()

    def test_path_is_shared_across_worktrees_and_ignored(self):
        a = run(self.wt, "work", "path", "T-1-cancel")
        b = run(self.main, "work", "path", "T-1-cancel")
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertEqual(a.stdout, b.stdout)
        self.assertEqual(Path(a.stdout.strip()), self.main / ".design" / "T-1-cancel")
        self.assertEqual((self.main / ".design" / ".gitignore").read_text(), "*\n")
        self.assertFalse((self.wt / ".design").exists())
        status = subprocess.run(["git", "-C", str(self.main), "status", "--porcelain"],
                                capture_output=True, text=True).stdout
        self.assertEqual(status, "")

    def test_log_appends_and_status_shows_approval_and_active(self):
        run(self.wt, "work", "log", "T-1", "승인", "사용자 '진행해'", "--step", "설계", agent="codex")
        run(self.wt, "work", "log", "T-1", "start", "재고 | 복원\n구현", "--step", "7-1", agent="codex")
        clash = run(self.main, "work", "log", "T-1", "시작", "같은 단계", "--step", "7-1")
        self.assertIn("작업 중", clash.stderr)
        self.assertIn("codex@wt:feat/x", clash.stderr)
        run(self.main, "work", "log", "T-1", "완료", "끝", "--step", "7-1")
        text = (self.main / ".design" / "T-1" / "PROGRESS.md").read_text(encoding="utf-8")
        self.assertEqual(sum(line.startswith("| 2") for line in text.splitlines()), 4)
        self.assertIn("재고 \\| 복원 구현", text)
        out = run(self.wt, "work", "status", "T-1").stdout
        self.assertIn("설계 승인:", out)
        self.assertIn("사용자 '진행해'", out)
        self.assertIn("작업 중: codex@wt:feat/x · 7-1", out)
        self.assertNotIn("작업 중: claude@main", out)

    def test_status_reads_plan_state_and_open_steps(self):
        folder = Path(run(self.main, "work", "path", "T-2").stdout.strip())
        (folder / "PLAN.md").write_text(
            "# x\n\n> 상태: 구현 중 · 기준 커밋: `abc`\n\n## 7. 구현 순서\n- [x] 1. 엔티티\n- [ ] 2. 서비스\n\n"
            "## 8. 대안\n- [ ] 세지 않는다\n", encoding="utf-8")
        out = run(self.wt, "work", "status", "T-2").stdout
        self.assertIn("상태: 구현 중", out)
        self.assertIn("구현 순서 1/2", out)
        self.assertIn("- [ ] 2. 서비스", out)
        self.assertIn("설계 승인: 기록 없음", out)
        listing = run(self.wt, "work", "list").stdout
        self.assertIn("T-2 — 상태 구현 중 · 구현 순서 1/2 · PLAN.md", listing)

    def test_template_state_line_is_not_read_as_a_state(self):
        folder = Path(run(self.main, "work", "path", "T-3").stdout.strip())
        template = (ROOT / "skills" / "feature-implementation" / "templates" / "PLAN.md").read_text(encoding="utf-8")
        (folder / "PLAN.md").write_text(template, encoding="utf-8")
        self.assertIn("상태: 초안", run(self.main, "work", "status", "T-3").stdout)

    def test_documents_left_in_a_worktree_are_listed_as_local(self):
        (self.wt / ".design" / "old").mkdir(parents=True)
        (self.wt / ".design" / "old" / "PLAN.md").write_text("# old\n", encoding="utf-8")
        self.assertIn("old (이 worktree 에만 있음)", run(self.wt, "work", "list").stdout)
        self.assertIn("과제 문서 없음", run(self.main, "work", "list").stdout)

    def test_bad_slug_and_event_are_rejected(self):
        self.assertNotEqual(run(self.main, "work", "path", "../x").returncode, 0)
        self.assertNotEqual(run(self.main, "work", "log", "T-1", "끝남", "x").returncode, 0)
        self.assertFalse((self.main.parent / "x").exists())

    def test_work_dir_override(self):
        shared = self.main.parent / "shared"
        out = run(self.wt, "work", "path", "T-4", env={"KNACK_WORK_DIR": str(shared)})
        self.assertEqual(Path(out.stdout.strip()), shared / "T-4")
        self.assertFalse((shared / ".gitignore").exists())

    def test_git_config_workdir_is_shared_by_every_worktree(self):
        shared = self.main.parent / "team"
        git(self.main, "config", "knack.workdir", str(shared))
        a, b = run(self.wt, "work", "path", "T-6"), run(self.main, "work", "path", "T-6")
        self.assertEqual(a.stdout, b.stdout)
        self.assertEqual(Path(a.stdout.strip()), shared / "T-6")

    def test_session_id_separates_two_sessions_in_one_worktree(self):
        env = {"KNACK_AGENT": "", "CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "ab12-cd34"}
        run(self.main, "work", "log", "T-7", "시작", "a", "--step", "7-1", env=env)
        other = run(self.main, "work", "log", "T-7", "시작", "b", "--step", "7-1",
                    env=dict(env, CLAUDE_CODE_SESSION_ID="ff99-0000"))
        self.assertIn("claude#ab12@main", other.stderr)
        self.assertIn("claude#ff99@main", other.stdout)

    def test_old_open_start_is_flagged_as_possibly_dead(self):
        folder = Path(run(self.main, "work", "path", "T-8").stdout.strip())
        (folder / "PROGRESS.md").write_text("| 2020-01-01 10:00 | codex@wt:x | 시작 | 7-1 | 옛 작업 |\n", encoding="utf-8")
        self.assertIn("끊긴 세션일 수 있다", run(self.main, "work", "status", "T-8").stdout)

    def test_sync_merges_worktree_only_documents(self):
        run(self.main, "work", "log", "T-9", "승인", "ok", "--step", "설계")
        local = self.wt / ".design" / "T-9"
        local.mkdir(parents=True)
        (local / "PROGRESS.md").write_text("| 2026-01-02 10:00 | codex@wt:x | 완료 | 7-1 | 샌드박스 안에서 |\n", encoding="utf-8")
        (local / "PLAN.md").write_text("# plan\n", encoding="utf-8")
        out = run(self.wt, "work", "sync")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        shared = self.main / ".design" / "T-9"
        text = (shared / "PROGRESS.md").read_text(encoding="utf-8")
        self.assertIn("승인", text)
        self.assertIn("샌드박스 안에서", text)
        self.assertEqual((shared / "PLAN.md").read_text(encoding="utf-8"), "# plan\n")
        self.assertFalse(local.exists())
        (local).mkdir(parents=True)
        (local / "PLAN.md").write_text("# different\n", encoding="utf-8")
        clash = run(self.wt, "work", "sync", "T-9")
        self.assertEqual(clash.returncode, 1)
        self.assertEqual((shared / "PLAN.md").read_text(encoding="utf-8"), "# plan\n")
        self.assertTrue((local / "PLAN.md").exists())

    def test_run_codex_adds_the_shared_folder_only_from_another_worktree(self):
        args = ("run", "main", "--agent", "codex", "--print", "--dry-run", "--", "x")
        from_wt = run(self.wt, *args).stdout
        self.assertIn(f"--add-dir {self.main / '.design'}", from_wt)
        self.assertNotIn("--add-dir", run(self.main, *args).stdout)
        self.assertFalse((self.main / ".design").exists())

    def hook(self, cwd):
        import json
        p = subprocess.run([sys.executable, str(ROOT / "hooks" / "knack-work" / "open_tasks.py")],
                           input=json.dumps({"cwd": str(cwd)}), capture_output=True, text=True,
                           env=dict(os.environ, KNACK_AGENT="claude", **GIT_ENV))
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"] if p.stdout.strip() else ""

    def test_session_hook_lists_open_tasks_only(self):
        self.assertEqual(self.hook(self.wt), "")
        open_ = Path(run(self.main, "work", "path", "T-open").stdout.strip())
        (open_ / "PLAN.md").write_text("# x\n> 상태: 구현 중 · 기준 커밋: `a`\n", encoding="utf-8")
        run(self.main, "work", "log", "T-open", "시작", "재고 복원", "--step", "7-2", agent="codex")
        done = Path(run(self.main, "work", "path", "T-done").stdout.strip())
        (done / "PLAN.md").write_text("# x\n> 상태: 완료 · 기준 커밋: `a`\n", encoding="utf-8")
        old = Path(run(self.main, "work", "path", "T-old").stdout.strip())
        (old / "PLAN.md").write_text("# x\n> 상태: 구현 중\n", encoding="utf-8")
        os.utime(old / "PLAN.md", (0, 0))
        text = self.hook(self.wt)
        self.assertIn("끝나지 않은 과제 문서 1건", text)
        self.assertIn("T-open — 상태 구현 중", text)
        self.assertIn("작업 중 codex@main", text)
        self.assertNotIn("T-done", text)
        self.assertNotIn("T-old", text)

    def test_session_hook_is_silent_on_bad_input(self):
        p = subprocess.run([sys.executable, str(ROOT / "hooks" / "knack-work" / "open_tasks.py")],
                           input="not json", capture_output=True, text=True, cwd=str(self.main.parent))
        self.assertEqual((p.returncode, p.stdout), (0, ""))

    def test_gate_runs_in_calling_worktree_and_records_commit(self):
        folder = Path(run(self.main, "work", "path", "T-5").stdout.strip())
        gates = folder / "GATES.md"
        gates.write_text("- [ ] G1: worktree 의 코드를 본다\n  CHECK: test -f only-wt.flag && echo yes\n  EXPECT: yes\n",
                         encoding="utf-8")
        (self.wt / "only-wt.flag").write_text("", encoding="utf-8")
        from_main = run(self.main, "gate", "run", str(gates))
        self.assertEqual(from_main.returncode, 1, from_main.stdout)
        from_wt = run(self.wt, "gate", "run", str(gates))
        self.assertEqual(from_wt.returncode, 0, from_wt.stdout + from_wt.stderr)
        self.assertIn("실행 위치:", from_wt.stdout)
        self.assertRegex(gates.read_text(encoding="utf-8"), r"result=pass .* commit=[0-9a-f]{7,}")


if __name__ == "__main__":
    unittest.main()
