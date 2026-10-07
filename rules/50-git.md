---
name: git
description: Git 작업 규칙 — 커밋·브랜치·푸시·PR
load: on-demand
when: 커밋·브랜치·푸시·PR 작업 전
---
# Git 작업
- 커밋·푸시·PR 생성은 사용자가 요청할 때만 한다. 기본 브랜치에 있으면 작업 브랜치를 먼저 만든다.
- 커밋 메시지는 레포의 기존 형식(`git log --oneline -20`)을 따른다. 형식이 없으면 Conventional Commits(`feat:`, `fix:` …)를 쓴다.
- 한 커밋에는 한 가지 목적만 담는다. 포맷 변경과 기능 변경을 섞지 않는다.
- `push --force`, `reset --hard`, 히스토리 재작성은 명시적 요청 없이 하지 않는다.
- PR 설명에는 변경 요약, 주요 결정, 검증 방법을 적는다. `.design/`의 `SUMMARY.md`가 있으면 활용한다.
- PR은 원격 호스트가 github.com이 아닌 레포(회사 git)에서는 로컬(`gh pr create` 등)에서 만들지 않는다. `git remote get-url origin`으로 호스트를 먼저 확인하고, 브랜치 push까지만 한 뒤 PR 생성은 사용자가 원격 플랫폼(GitHub Enterprise·Azure DevOps 등)에서 직접 하도록 안내한다.
- 개인 github.com 레포에서는 `gh pr create`로 PR을 만들어도 된다.
