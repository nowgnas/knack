---
name: obsidian-ticket
description: 티켓 관련 작업 시작 시 Obsidian 티켓 노트를 먼저 읽는다
load: on-demand
when: 브랜치명에 JIRA 스타일 티켓 키가 있거나 사용자가 티켓 번호를 언급하는 등 티켓 관련 작업을 시작할 때
---
# Obsidian 티켓 노트 선확인

- 현재 브랜치명에 `[A-Z][A-Z0-9]+-\d+` 형태의 티켓 키가 있으면(예: `feature/CONSUMER-286`, `bugfix/FRDEV-6781`) 티켓 관련 작업으로 본다. 브랜치에 없으면 사용자가 대화에서 같은 형태의 티켓 번호를 직접 언급했을 때만 적용한다. 둘 다 아니면 이 룰은 적용하지 않는다.
- 적용 대상이면 작업을 진행하기 전에 Obsidian의 해당 티켓 노트를 먼저 찾아 읽는다.
- vault 경로는 `~/.config/knack/obsidian-vault.local.yml`의 `vault_path`와 `work.folder`(기본값 `Work`)를 쓴다. 설정이 없으면 임의 경로를 추정하지 말고 사용자에게 `obsidian-daily` 룰의 설정 방법을 안내한다.
- 노트 파일은 `{vault_path}/{work.folder}/` 아래 연도별 하위 폴더에 `{티켓키}-<제목>.md` 형태로 있다. 정확한 하위 경로를 모르므로 `find`나 `rg --files` 로 파일명에 티켓 키가 들어간 파일을 재귀적으로 찾는다.
- 못 찾으면 작업을 막지 않는다 — 노트를 찾지 못했다고 한 줄로 알리고 평소대로 진행한다. 여러 개가 매치되면 사용자에게 확인한다.
- 찾았으면 frontmatter(`jira`, `status`, `service`, `deploy`, `related`)와 `Background`·`Design & Decisions`·`Remaining` 섹션을 읽어 작업 배경·의도·남은 일을 파악하고 이후 작업에 반영한다.
- 노트 내용을 레포로 복사하거나 커밋하지 않는다. 같은 세션에서는 이미 읽은 노트를 다시 찾지 않는다.
