# Changelog

## [Unreleased]

### Added
- Add an on-demand Obsidian Daily rule with user-local vault and TODO configuration.
- Add a generic Obsidian vault configuration template without personal paths or note content.
- Add GitHub Copilot CLI as an install target: skills via the shared `~/.agents/skills`, rules in a block in `~/.copilot/copilot-instructions.md` (respects `COPILOT_HOME`).
- Add a reverse direction to `trace-flow`: find every place that touches a table, topic, cache key or config key, with reads and writes separated and the gaps in the search stated.
- Add candidate model lists (`"model": ["gpt-6-astra", "gpt-6-sol"]`) and a machine-local override at `~/.config/knack/models.local.json`, so a PC without a pinned model still resolves one.
- Add an `overlaps:` field to skills and a functional-overlap report in `knack doctor`, for external skills that answer the same request under a different name.
- Add a `when:` field to subagents so the delegation condition ships with the routing index.
- Add a ladder to the coding rule: stop at the first rung that works, and justify any new dependency or layer in the plan.
- Add a stopping policy and a report order to the core rule: keep going when no user input is needed, and put decisions the user owns first.

### Changed
- Make the new-rule smoke test validate the path returned by `knack new rule` instead of assuming a fixed rule number.
- Replace `DESIGN.md` + `SUMMARY.md` + `REVIEW.md` with a single `PLAN.md` that gains a result section after implementation; keep `GATES.md` and `REVIEW.md` for high-risk work only, and widen the lightweight tier so small changes write no file.
- Judge writes in the guard hook by command name and redirect target instead of any mention of a protected path, treating quoted strings and heredoc bodies as data; protect the `knack:start` block in instruction and config files, allowing edits outside it.
- Run `knack doctor` at the end of `knack update`, and stop before installing when the pull fails.

### Fixed
- Count plugin skills from the plugin manifest, falling back to a recursive scan, so plugins that nest skills one level deeper are no longer reported as empty.
- Keep the model routing index in the Codex instruction block: `tier_rank_of` assumed a single model name and crashed on candidate lists, and `install.sh` hid the failure.
