# Changelog

## [Unreleased]

### Added
- Add an on-demand Jira and Confluence creation rule that checks for write-capable tools and verifies created items.
- Add an on-demand Obsidian Daily rule with user-local vault and TODO configuration.
- Add a generic Obsidian vault configuration template without personal paths or note content.

### Changed
- Make the new-rule smoke test validate the path returned by `knack new rule` instead of assuming a fixed rule number.
