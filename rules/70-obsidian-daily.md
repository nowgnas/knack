---
name: obsidian-daily
description: Obsidian 업무용 Daily 노트를 사용자별 vault 경로와 TODO 설정에 따라 읽고 작성
load: on-demand
when: Obsidian 업무 vault의 Daily 노트를 읽거나 만들거나 갱신할 때
---
# Obsidian 업무 Daily

- 사용자 설정은 `~/.config/knack/obsidian-vault.local.yml`에서 읽는다. 공유 가능한 기본 양식은 `~/knack/templates/obsidian-vault.local.yml.example`이다. 이 양식은 개인 vault 경로·일정·노트 내용을 담지 않는다.
- 설정에 지정된 vault 경로와 Daily 경로 패턴만 사용한다. 설정이 없거나 경로가 없으면 임의의 위치를 찾지 말고 사용자에게 설정 방법을 안내한다.
- 사용자별 설정 파일의 vault 경로, TODO 선호, 노트 내용은 `~/knack`에 복사하거나 커밋하지 않는다. 사용자가 직접 요청하지 않는 한 vault 외부로 노트를 복사하거나 공유하지 않는다.
- 기존 Daily 노트를 작성할 때의 기본 형태는 YAML frontmatter의 `type: daily`, `date: YYYY-MM-DD`, 날짜 제목, `To Do`, `Log`, `Notes`, `Tomorrow` 섹션이다. 사용자 설정이 이 구조나 이름을 바꾸면 설정을 우선한다.
- TODO 섹션명, 체크박스 표기, 기본 항목, 미완료 항목 이월 여부·표시 문구는 사용자 설정을 따른다. 완료되지 않은 항목을 임의로 완료 처리하거나 삭제하지 않는다. 설정이 없으면 기존 일일 노트의 TODO 형식만 참고하고, 사용자별 이월 동작은 추정하지 않는다.
- 새 Daily 파일을 만들기 전 같은 날짜 파일이 있는지 확인한다. 이미 있으면 중복 생성하지 말고 사용자 요청에 따라 기존 파일을 갱신한다.
