---
name: knack-manage
description: 스킬·룰·훅·서브에이전트·모델 라우팅을 하네스로 관리한다. "이 스킬 설치해줘", "하네스 업데이트" 같은 요청에 사용.
---

# Harness Manage

에이전트 설정의 원본은 하네스 레포다. `~/.claude/skills`, `~/.agents/skills`, `~/.claude/agents`,
훅 설정 파일(`~/.claude/settings.json`, `~/.codex/hooks.json`), 지시 파일의 knack 블록에 직접 쓰지 않는다.
직접 쓰려고 하면 `guard-agent-config` 훅이 막는다.
세션 시작 때 `knack-stale` 훅이 "설치본이 레포와 다르다"고 알리면, 사용자에게 보고하고 `knack install --dry-run` → 승인 후 `knack install` 로 갱신한다(훅이 직접 설치하지는 않는다).

## 1. 조회 — 파일을 읽지 말고 CLI로
| 목적 | 명령 |
|---|---|
| 하네스 항목과 설치 상태 | `knack list` (종류: `skills`, `rules`, `agents`, `hooks`) |
| 외부 항목까지 (중복 확인) | `knack list --all`, `knack list skills --all` |
| 플러그인(Claude Code·데스크톱 앱), MCP 서버 | `knack list plugins`, `knack list mcp` |
| 항목 내용 | `knack show <종류> <이름> --toc` 후 `--section <번호\|제목>` |
| 키워드 | `knack search <키워드>` (`-l`: 파일별 개수만) |
| 구조·작성 기준·설치 점검 | `knack doctor` |
| 작업 유형별 모델 | `knack model` |

## 2. 요청별 절차
| 요청 | 절차 |
|---|---|
| 외부 스킬 설치 (경로, git URL) | 1) `knack list skills --all`로 같은·비슷한 스킬 확인, 겹치면 알린다 (기능이 겹치는데 둘 다 두기로 하면 하네스 스킬 frontmatter 의 `overlaps:` 에 외부 스킬 이름을 적어 doctor 가 알리게 한다) 2) `knack add skill <src> [--subdir P] [--name N]` 3) 출력의 "실행 가능한 파일"을 검토해 요약한다 4) description 이 160자를 넘으면 트리거를 유지한 채 줄인다(매 세션 로드되므로). 본문은 원본 그대로 둔다 — `.knack-source` 가 있는 스킬은 doctor 가 본문 길이를 검사하지 않는다 5) 설치 단계로 |
| 새 스킬·룰·훅 만들기 | `knack new skill\|rule\|hook <이름>` → 내용 작성 → 스킬이면 `skills/knack-help/USAGE.md`에 안내 추가 → `knack doctor`로 작성 기준 확인 → `knack test` → 설치 단계로 |
| 외부 스킬을 하네스로 옮기기 | 사용자가 요청할 때만 `knack adopt skill <이름>` → 설치 단계로 |
| 외부 스킬 제거 | 가드 훅이 막으므로 직접 지우지 않는다. `knack list skills --all`로 대상·위치를 확인하고, 백업 후 삭제하는 명령을 사용자에게 안내한 뒤 `knack list --all`로 결과를 확인한다 |
| 훅 켜기·끄기 | `knack hook enable\|disable <이름>` → 설치 단계로 |
| 작업 유형별 모델 변경 | `knack model`로 현재 표 확인 → `knack model set <작업\|main\|tier:이름> <티어\|모델> [--agent] [--effort]` → 설치 단계로. 새 위임 대상이 필요하면 `agents/`에 `task:`를 가진 서브에이전트를 만든다 |
| 룰 | always 룰은 매 세션 로드되므로 짧게 쓴다. 가끔 필요한 규칙은 on-demand 룰(`when:`에 읽을 시점)로 만든다 |
| 플러그인·MCP | 하네스는 조회만 한다. 설치는 각 에이전트 명령으로 하되 사용자에게 알린다. 데스크톱 앱(Cowork) 플러그인은 앱 설정에서 켜고 끈다 |

## 3. 설치 단계
1. `knack install --dry-run`으로 변경 예정 사항을 보여주고, **사용자 승인 후** `knack install`을 실행한다.
   - 특정 레포에만: `--project <path>`. 특정 에이전트만: `--agents claude|codex|copilot` (copilot 은 스킬·룰만).
   - 업데이트: `knack update` (git pull + 재설치). 제거: `knack uninstall`.
2. `knack status`나 `knack doctor`로 결과를 확인해 보고한다.
3. 충돌로 건너뛴 항목(`SKIP`)은 그대로 알리고, 덮어쓸지(`--force`, 백업 후 교체) 묻는다.
4. 하네스 레포를 바꿨으면 `knack test`로 검증한 뒤 커밋을 제안한다. push는 요청이 있을 때만 한다.
5. 새 스킬·룰·훅은 새 에이전트 세션부터 적용된다. Codex는 새 훅을 처음 실행할 때 신뢰 확인을 요청한다.
