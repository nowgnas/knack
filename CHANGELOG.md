# Changelog

## [Unreleased]

### Added
- Add the `mistake-proofing` skill: `bug-fix` records now carry a `mistake:<slug>` tag; `scripts/mistakes.py list|check` counts tags across `BUGFIX.md` files (no state file) and fails when a tag seen twice has no row in `docs/enforcement.md`. The skill picks the strongest enforcement (types, ArchUnit / NetArchTest, analyzers, tests, CI), proves it fails on the code that had the mistake, records rule · enforcement · command · proof, and removes the duplicated instruction. Ideas adapted from pstack (MIT); see `THIRD_PARTY_NOTICES.md`.
- Add the `verification-skill` skill: it generates a repo-local `verify-<app>` skill (launch, doctor, drive, evidence, cleanup, a feature map) for Spring Boot and .NET apps from what the repo shows, runs it once end to end and records the run in `EVIDENCE.md` (otherwise it stays "unproven"), and audits an existing one (link or copy sync, per-feature source check, a live pass over every feature, outcome clean / changed / blocked). The canonical copy lives in `.agents/skills/`, `.claude/skills/` gets a relative symlink or a copy checked by sha256 (`scripts/link_skill.py`). Ideas adapted from pstack (MIT); see `THIRD_PARTY_NOTICES.md`.
- Add proof levels to `impl-review`: every 🔴 and 🟠 carries a level from 1 (stated) to 5 (reproduced); findings settled by reading are confirmed at level 2, and a runtime-behavior one below level 4 is reported as a latent finding with a proof request (command, defect criterion). The implementer or `verifier` runs it on a clean tree and records `증명 · 실행 · commit · 작업트리 · cmd · exit · 출력`; only a run that meets the "no defect" criterion rebuts it, one no safe command can decide goes to the user, and no merge happens while a latent 🔴/🟠 is open. The checklist gains a blast-radius item (the one safety fact, grep-invisible surfaces, cleared risks). Ideas adapted from pstack (MIT); see `THIRD_PARTY_NOTICES.md`.
- Add the `stack-verify` skill: `scripts/detect.py` finds Gradle, Maven and .NET build units and emits their format, compile, single-test, test and migration commands as JSON (`schema_version` 1) with the evidence files; the skill runs them fastest-first, checks migrations only against local or Testcontainers DBs, and reports each command's result.
- Add the `guard-prod-ops` hook (Claude and Codex): it fails closed on migrations aimed at a non-local DB (`dotnet ef database update/drop`, Flyway, Liquibase, their Gradle and Maven plugins, Docker images) and on runs with a production environment or profile. Allowed targets are local hosts, Testcontainers, in-memory DBs, project SQLite files and hosts listed in `.knack/safe-db-hosts`. The shell parser shared with `guard-agent-config` moves to `hooks/_shared/shellparse.py`.
- Add an on-demand Obsidian Daily rule with user-local vault and TODO configuration.
- Add a generic Obsidian vault configuration template without personal paths or note content.
- Add GitHub Copilot CLI as an install target: skills via the shared `~/.agents/skills`, rules in a block in `~/.copilot/copilot-instructions.md` (respects `COPILOT_HOME`).
- Add a reverse direction to `trace-flow`: find every place that touches a table, topic, cache key or config key, with reads and writes separated and the gaps in the search stated.
- Add candidate model lists (`"model": ["gpt-6-astra", "gpt-6-sol"]`) and a machine-local override at `~/.config/knack/models.local.json`, so a PC without a pinned model still resolves one.
- Add an `overlaps:` field to skills and a functional-overlap report in `knack doctor`, for external skills that answer the same request under a different name.
- Add a `when:` field to subagents so the delegation condition ships with the routing index.
- Add a ladder to the coding rule: stop at the first rung that works, and justify any new dependency or layer in the plan.
- Add a stopping policy and a report order to the core rule: keep going when no user input is needed, and put decisions the user owns first.

### Removed
- Remove `knack bench` (`lib/bench.py`, `bench/`): the fixed baseline → knack order, the HOME mirror that still links most of the real HOME, and the `git worktree remove --force` path built from task IDs made its numbers hard to trust and its cleanup risky. Existing `~/.knack-bench/` (or `~/.harness-bench/`) folders are left alone; delete them by hand if no longer needed.
- Remove `knack usage` (`lib/usage.py`) and `usage_weights` in `models.json`: per-skill totals added each session's full tokens to every skill it used, `--since` selected whole sessions by file time, and session collection and token metrics move to a separate tool outside the harness. A leftover `usage_weights` in a local `models.local.json` is ignored.
- Remove keyword task classification: `knack model which`, `knack run auto`, and `tasks.*.keywords` in `models.json`. Substring matching on a handful of keywords had no accuracy data; pick the task type explicitly with `knack run <task|main>`. Extra `keywords` fields in a local `models.local.json` are ignored.
- Remove `knack add skill --install`: it ran `install.sh --global` right after copying third-party files, with no dry-run and no review step. `add skill` now always ends with the `knack install --dry-run → knack install` hint.

### Changed
- Make the new-rule smoke test validate the path returned by `knack new rule` instead of assuming a fixed rule number.
- Replace `DESIGN.md` + `SUMMARY.md` + `REVIEW.md` with a single `PLAN.md` that gains a result section after implementation; keep `GATES.md` and `REVIEW.md` for high-risk work only, and widen the lightweight tier so small changes write no file.
- Judge writes in the guard hook by command name and redirect target instead of any mention of a protected path, treating quoted strings and heredoc bodies as data; protect the `knack:start` block in instruction and config files, allowing edits outside it.
- Run `knack doctor` at the end of `knack update`, and stop before installing when the pull fails.

### Fixed
- Count plugin skills from the plugin manifest, falling back to a recursive scan, so plugins that nest skills one level deeper are no longer reported as empty.
- Keep the model routing index in the Codex instruction block: `tier_rank_of` assumed a single model name and crashed on candidate lists, and `install.sh` hid the failure.
- Stop the guard hook from blocking edits to the harness repo itself and to files that only mention a block marker: blocks are recognised only by markers at the start of a line, and the harness repo is exempt.
- Close guard hook bypasses: a here-string (`<<<`) no longer hides the following lines, `env`/`xargs`/`nice` are unwrapped, and `find -delete`/`-exec <write>` count as writes.
- Judge `cp`/`ln`/`install`/`rsync` by their destination only and `tar -c` by its archive file, so backing up a protected file or folder is no longer blocked (`mv` still checks its source).
