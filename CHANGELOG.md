# Changelog

## [Unreleased]

### Added
- Add an on-demand Obsidian Daily rule with user-local vault and TODO configuration.
- Add a generic Obsidian vault configuration template without personal paths or note content.
- Add GitHub Copilot CLI as an install target: skills via the shared `~/.agents/skills`, rules in a block in `~/.copilot/copilot-instructions.md` (respects `COPILOT_HOME`).

### Changed
- Make the new-rule smoke test validate the path returned by `knack new rule` instead of assuming a fixed rule number.
