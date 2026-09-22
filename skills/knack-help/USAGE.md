# knack 사용법

knack 은 백엔드 개발용 개인 에이전트 하네스입니다. 에이전트(Claude Code, Codex)의 **스킬·룰·훅·서브에이전트**를 이 레포 하나에서 관리합니다.
요청 문장에 맞는 스킬이 자동으로 선택되고, 직접 부를 수도 있습니다.
기본 개발 절차는 knack 스킬(`feature-implementation`, `bug-fix`, `impl-review`)이고, superpowers와 unlazy의 검증 규율을 이 안에 흡수했습니다. 무엇을 어디서 가져왔는지는 README의 "작업 규율"에 있습니다.

- **Claude Code**: `/스킬이름` (예: `/repo-onboarding quick`)
- **Codex**: 프롬프트에 `$스킬이름`으로 언급하거나 `/skills`에서 선택

## 상황별 사용법

| 상황 | 이렇게 요청 | 스킬 | 결과물 |
|---|---|---|---|
| 처음 보는 레포 | "이 레포 파악해줘", "quick으로 온보딩", "deep 모드로 결제 도메인 위주로" | `repo-onboarding` | `.onboarding/ONBOARDING.md` 외 |
| API 동작 이해 | "POST /api/orders 흐름 따라가줘" | `trace-flow` | `.onboarding/flows/*.md` |
| 새 기능 | "주문 취소 API 추가해줘" (요구사항·정책 문서가 있으면 함께) | `feature-implementation` | `.design/<날짜>-<slug>/DESIGN.md`, `SUMMARY.md` |
| 버그 | "이 버그 고쳐줘", "이 에러 고쳐줘" + 스택트레이스·로그 | `bug-fix` | `.design/<날짜>-bug-<slug>/BUGFIX.md` |
| 머지 전 리뷰 | "머지 전에 리뷰해줘" | `impl-review` | `.design/.../REVIEW.md` |
| 스킬·룰·훅 설치·관리 | "이 스킬 설치해줘", "훅 추가해줘", "하네스 업데이트해줘" | `knack-manage` | 하네스 레포 변경 |
| 내 정보 등록 | "내 정보 등록해줘", "페르소나 수정해줘" (자기소개 파일이 있으면 함께) | `persona` | `persona/core.md`, `persona/detail/*.md` |
| 쉬운 말로 설명 | "이거 매니저한테 설명하려면", "ELI5로 설명해줘" | `eli5` | — |
| 사용법 | "하네스 사용법 알려줘" | `knack-help` | — |

## 스킬별 요약

### repo-onboarding — 처음 보는 레포 파악
- 모드: `quick`(0~2단계, 5분 내외) / `standard`(기본, 0~6단계) / `deep`(0~7단계, 리스크 분석)
- 단계: 스캔 → 큰 그림 → 진입점 → 핵심 흐름 → 데이터 → 연동 → 운영 → 리스크
- 재실행하면 문서에 기록된 기준 커밋 이후의 변경분만 갱신합니다.

### persona — 사용자 페르소나 정리
- 원자료(대화·자기소개 파일)를 **결정 형태**로 바꿔 저장합니다. "10년차 시니어" → 버림, "새 의존성은 먼저 묻는다" → `defaults`
- core(매 세션 주입, 15줄 이내)와 상세(`persona show <주제>` 로 필요할 때)를 나눕니다
- 저장 후 사용자 승인을 받아 `knack install` 로 반영합니다

### trace-flow — 요청 흐름 추적
- 입력: `METHOD /path`, 토픽·큐 이름, 배치 잡, `Class.method`
- 출력: 시퀀스 다이어그램, 단계별 표(`path:line`), 데이터 변경, 부수효과, 실패 경로

### feature-implementation — 기능 구현
```
요구사항 정리 → 정책 점검(✅/❓/⚠️) → 컨벤션 파악 → 구현 설계 (+ 고위험이면 GATES.md)
  → [게이트] 질문 해소 + 설계 승인 + 테스트 계획 합의 (+ 고위험이면 게이트 명령 승인)
  → 구현 (성공 기준 테스트의 실패를 먼저 확인) → 검증 (고위험이면 knack gate run)
  → 셀프 리뷰 4단계 → 독립 리뷰 → 보고 직전 knack gate reverify (고위험) → 핵심 구현 요약
```
- 게이트를 통과하기 전에는 코드를 수정하지 않습니다. 설계가 괜찮으면 "진행해"처럼 **명시적으로 승인**해 주세요.
- 승인 뒤에는 로컬 빌드·테스트·린트 실행과 실패 수정을 묻지 않고, 완료 기준(테스트·린트 통과, 독립 리뷰 반영, 요약)까지 진행한 다음 한 번 보고합니다.
- 작은 변경은 경량 모드로, 설계를 5줄로 요약해 확인받습니다. "설계 없이 바로 해줘"라고 하면 게이트를 건너뜁니다(가정은 요약에 남음).
- 스키마가 바뀌면 DB 마이그레이션 가이드(expand → contract, 락, 롤백)가 설계에 적용됩니다.
- 성공 기준 테스트는 구현 전에 실패하는 것부터 확인하고(Red → Green), 리뷰 전에 완성도 → 도메인 전문가의 눈 → 결함 사냥 → 정리 순서로 셀프 리뷰합니다.
- **고위험 변경**(스키마·데이터 보정, 금액·결제·정산, 동시성·멱등성, 메시지 재처리, 대규모 리팩터링)은 설계 때 완료 게이트 `GATES.md`를 함께 승인받고, 완료 보고 직전에 `knack gate reverify`로 전부 다시 확인합니다. 규칙: `knack show ref high-risk-gates`

### bug-fix — 버그 수정
- 원인을 입증하기 전에는 고치지 않습니다. 재현 테스트를 먼저 만듭니다.
- 동작·정책 변경, API·스키마 변경, 데이터 보정, 3개 파일 초과, 추정 수정 중 하나라도 해당하면 승인 후 수정합니다.
- 잘못 저장된 데이터가 있으면 조회 쿼리와 보정 스크립트 **초안**만 만듭니다. 실행은 사람이 합니다.
- 가설은 한 번에 하나씩, 여러 컴포넌트를 거치면 경계마다 증거를 모읍니다. 수정을 되돌리면 재현 테스트가 다시 실패하는지까지 확인합니다.
- 수정 시도가 세 번 실패하면 네 번째 수정 대신 구조 문제로 보고 방향을 정합니다. 고위험 영역이면 기능 구현과 같은 완료 게이트를 씁니다.

### impl-review — 독립 리뷰
- 구현 맥락이 없는 리뷰어가 diff를 설계 문서, 레퍼런스 기능, 체크리스트와 대조합니다.
  - Claude: `impl-reviewer` 서브에이전트
  - Codex: `codex exec -s read-only` 새 세션
- 심각도는 🔴 Blocker · 🟠 Major · 🟡 Minor · ⚪ Nit · ❔ 질문 다섯 단계입니다. 🔴·🟠는 반영하고, 리뷰는 최대 2라운드까지 합니다.
- 리뷰어는 구현자의 요약을 믿지 않고 성공 기준을 코드와 한 줄씩 대조합니다. 구현자는 지적을 반영하기 전에 코드로 사실인지 확인하고, 틀리면 근거를 들어 반박합니다.

### knack-manage — 스킬·룰·훅 관리
- 스킬을 설치할 때 에이전트 폴더에 바로 넣지 않고 하네스에 추가한 뒤 `knack install`로 연결합니다.
- 설치 전에 `knack list --all`로 하네스와 외부에 이미 있는 스킬(같은 이름, 플러그인 스킬 포함)을 확인합니다.
- 에이전트 폴더에 직접 설치하려고 하면 `guard-agent-config` 훅이 막고 하네스 명령을 안내합니다.
- 외부 스킬·플러그인은 `knack list --all`로 봅니다. 데스크톱 앱(Cowork)에서 설치한 플러그인과 앱 기본 제공 스킬도 포함되며, 이들은 앱 설정에서 켜고 끕니다.
- 외부 스킬 제거도 가드 훅이 막습니다. 에이전트가 대상을 확인해 백업·삭제 명령을 안내하면 사용자가 실행하고, 에이전트가 `knack list --all`로 결과를 확인합니다.

### eli5 — 청중에 맞춘 설명 (외부 스킬)
- 출처: [DreambigOu/ELI5](https://github.com/DreambigOu/ELI5) (MIT). `knack add skill`로 가져왔고 원본 내용은 그대로입니다.
- 청중을 나이·학년·직무·관계 중 하나로 잡고 어휘·비유·톤·깊이를 맞춥니다. 청중을 안 적으면 "5살"이 기본입니다.
- 설명 구조: 한 줄 정의 → 비유 → 청중 수준에 맞는 세부 → "그래서 나한테 뭐가 달라지나".
- 코드·에러 메시지도 대상입니다. 먼저 원본을 읽고 목적부터, 그다음 동작 순서로 설명합니다.

## 완료 게이트 — 고위험 변경

스키마·데이터 보정, 금액·결제·정산, 동시성·멱등성, 메시지 재처리, 대규모 리팩터링처럼 "테스트 몇 개 통과"로 완료를 판단하기 어려운 변경에 씁니다.
설계 때 `.design/<slug>/GATES.md`를 함께 승인받고, 완료 보고 직전에 전부 다시 실행합니다.

```markdown
- [ ] G1: 같은 멱등키로 동시에 10건 요청하면 결제 승인은 1건이다
  CHECK: ./gradlew test --tests '*PaymentIdempotencyIT*'
  EXPECT: BUILD SUCCESSFUL
- [ ] G2: 배포 순서(Expand → 배포 → Contract)를 팀과 합의했다
  EVIDENCE: pending
```

- 게이트 하나에 관찰 가능한 결과 하나를 씁니다. 자동 게이트는 `exit 0`과 `EXPECT` 일치를 둘 다 만족해야 통과입니다. 수동 게이트(G2)는 명령으로 판정할 수 없을 때만 쓰고, 확인한 뒤 체크하고 `EVIDENCE:`에 사실 한 줄을 적습니다.
- `knack gate status`는 실행하지 않고 상태만 봅니다. `run`은 미충족 게이트만, `reverify`는 충족된 것까지 전부 다시 실행합니다. 게이트 정의를 바꾸면 이전 증거는 무효가 됩니다.
- 불가능한 게이트는 지우지 않고 맨 앞 열에 `ABANDON: <id> <이유와 인계 대상>`을 적습니다. 포기가 있으면 완료가 아니라 인계로 보고합니다.
- `echo ok`처럼 코드와 상관없이 통과하는 게이트는 `knack gate`가 경고합니다.
- 규칙 전체: `knack show ref high-risk-gates` · 템플릿: `knack show template GATES`

## 룰과 훅

| 종류 | 위치 | 적용 방식 |
|---|---|---|
| always 룰 | `rules/*.md` (`load: always`) | Claude: `CLAUDE.md`에 import / Codex: `AGENTS.md`에 본문 블록. 매 세션 로드되므로 짧게 유지 |
| on-demand 룰 | `rules/*.md` (`load: on-demand`, `when:`) | 지시 파일에는 이름과 시점 한 줄만 들어가고, 본문은 필요할 때 `knack show rule <이름>`으로 읽음 |
| 훅 | `hooks/<이름>/hook.json` + 스크립트 | `settings.json`(Claude), `hooks.json`(Codex)에 `--knack-hook` 표식이 붙은 항목만 추가·제거. 다른 훅은 건드리지 않음 |

기본 훅 `guard-agent-config`는 `~/.claude/skills`, `~/.agents/skills`, `~/.codex/skills`, `~/.claude/agents`에 직접 쓰는 것을 막습니다. 하네스로 이어지는 링크를 통한 수정은 허용합니다. 끄려면 `knack hook disable guard-agent-config` → `knack install`.

기본 훅 `knack-stale`(Claude `SessionStart`)은 설치본이 레포와 다르면 세션 시작 때 알립니다. 스킬은 심링크라 레포를 고치면 바로 반영되지만 룰 블록·서브에이전트·훅·모델은 `install.sh`가 만드는 생성물이라 레포만 고치면 낡은 상태로 남기 때문입니다. 판단은 `install.sh --status`가 하고, 훅은 알리기만 합니다(설치는 사용자 승인 후 `knack install`). 끄려면 `knack hook disable knack-stale` → `knack install`.

## 작업 유형별 모델

`models.json`이 작업 유형(설계·구현·리뷰·탐색·git·문서·조회)마다 쓸 모델을 정합니다. 작업은 티어(deep / standard / fast)에 묶이고, 티어는 에이전트별 모델로 이어집니다. 현재 표는 `knack model`로 확인합니다.

| 적용 방식 | Claude Code | Codex |
|---|---|---|
| 위임 서브에이전트 (`agents/*.md`의 `task:`) | `~/.claude/agents/*.md`를 `model:`을 넣어 생성 | `~/.codex/config.toml`에 `[agents.<이름>]` 역할, `~/.codex/knack/agents/*.toml`에 모델·effort |
| 세션 기본 모델 (`main`) | `~/.claude/settings.json`의 `model` | `~/.codex/config.toml`의 `model`, `model_reasoning_effort` |
| 지시 파일 블록 | "커밋·푸시·PR → `git-ops`에 위임" 같은 색인 몇 줄 | 동일 (`spawn_agent`로 위임) |

- 커밋·푸시·PR은 `git-ops`, 탐색은 `repo-explorer`, 독립 리뷰는 `impl-reviewer`에 위임되고, 설계·구현은 세션 모델로 진행합니다.
- 스크립트로 고르기: `knack model which "<요청>"`(키워드 분류), `knack model get <작업> --agent codex --format flags`, `knack run auto -- "<요청>"`(맞는 모델로 새 세션 실행).
- 바꾸기: `knack model set git haiku --agent claude`, `knack model set implement deep`, `knack model set main deep --agent codex` → `knack install`.

## 사용자 페르소나

에이전트가 **되묻거나 잘못 추측할 것**을 미리 못 박아 두는 사실 모음입니다. 정체성·포부가 아니라 결정을 담습니다 —
"이 줄이 없으면 에이전트가 무엇을 잘못하거나 되묻는가?"에 답이 없는 줄은 넣지 않습니다.

| 명령 | 용도 |
|---|---|
| `knack persona init` → 템플릿 채우기 | `persona/core.md` 생성. 매 세션 지시 블록에 주입되므로 15줄 이내로 유지 |
| `knack persona set <키> "<값>"` | 항목 하나 수정·추가. 값에 `;` 를 쓰면 목록 (예: `set defaults "A; B"`) |
| `cat me.md \| knack persona import -` | 파일·표준입력으로 통째로 넣기 (스크립트 입력 경로) |
| `knack persona import --detail <주제> <파일>` | 주입하지 않는 상세. 이름만 색인되고 `knack persona show <주제>` 로 읽음 |
| `knack persona show [주제]` · `check` · `path` | 주입되는 내용 확인 · 형식·길이 점검 · 파일 경로 |
| `knack persona disable` / `enable` | 주입 끄기·켜기 (효과 측정용) |

- 형식은 `키: 값` 이고 기본 키는 `role`, `stack`, `work`, `goals`, `defaults`, `avoid` 입니다. 다른 키도 쓸 수 있습니다.
- 수정 후 `knack install` 을 해야 지시 블록에 반영됩니다. 잊으면 `knack-stale` 훅이 다음 세션에 알려 줍니다.
- `persona/core.md`·`persona/detail/` 은 개인 정보라 `.gitignore` 에 있습니다. 레포에는 템플릿만 커밋됩니다.
- 에이전트에게 "내 정보 등록해줘"라고 하면 `persona` 스킬이 원자료를 결정 형태로 정리해 저장합니다.
- 레포의 실제 코드가 페르소나와 어긋나면 에이전트는 레포를 믿고 사용자에게 알립니다. 낡은 페르소나는 없는 것보다 나쁩니다.
- 효과가 의심되면 측정합니다: `persona disable` → `bench run --label persona-off`, `persona enable` → `--label persona-on`, `bench compare`. 작업 세트에는 페르소나가 없으면 되묻을 작업을 넣습니다.

## 토큰 사용량 측정과 비교

| 명령 | 용도 |
|---|---|
| `knack usage [--since 7d] [--agent claude\|codex] [--here] [--by session\|model\|day\|skill\|cwd]` | 두 에이전트의 세션 로그에서 토큰(입력·캐시 쓰기·캐시 읽기·출력)과 가중 환산값을 집계 |
| `knack bench init` → `knack bench ab --repeat 2` | 같은 작업 세트를 baseline(하네스 제외)과 현재 설정으로 연달아 실행하고 토큰·check 통과율·턴·시간 비교표 출력 |
| `knack bench run [--baseline] --label <조건>` · `knack bench compare <A> <B>` | 조건 하나씩 실행하고 원하는 두 조건 비교 |

- weighted는 입력 토큰 기준 가중합입니다(캐시 읽기 0.1배, 출력 5~8배). 달러가 아닌 상대 비교용이며 `models.json`의 `usage_weights`에서 조정합니다.
- 벤치는 작업마다 git worktree를 만들어 비대화 모드(`claude -p`, `codex exec`)로 실행하고 끝나면 정리합니다(`--keep`으로 보존).
- 작업 파일 기본 위치는 `~/.knack-bench/tasks.json`입니다(`knack bench init`으로 생성).
- baseline은 전역 설정을 건드리지 않고 `~/.knack-bench/baseline-home`의 HOME 미러로 실행합니다. 하네스 스킬·서브에이전트, 지시 파일의 knack 블록, 하네스 훅, Codex 역할 블록만 빠지고 인증·프록시 설정·캐시·세션 로그 폴더는 원본 링크입니다. 빠지는 항목은 `knack bench baseline`으로 확인합니다.
- 에이전트에게 "하네스 벤치 돌려줘, repeat 2"라고 하면 `knack-manage` 절차로 작업 파일을 확인하고 `knack bench ab --repeat 2`를 실행합니다. 오래 걸리므로 Claude는 백그라운드로 실행하고, Codex는 샌드박스 밖 작업이라 명령을 안내합니다.
- 앱 세션(에이전트가 CLI를 중첩 실행) 안에서 돌릴 때 주의할 점:
  - 작업당 기본 타임아웃이 1800초라 포그라운드로는 세션 턴이 먼저 끊깁니다. `nohup knack bench ab --repeat 2 > ~/.knack-bench/ab.log 2>&1 &` 처럼 백그라운드로 돌리고 로그를 확인합니다.
  - baseline 조건은 `CLAUDE_CONFIG_DIR` 를 떼고 실행하지만 현재 설정 조건은 세션의 환경변수를 그대로 물려받습니다. 앱이 `CLAUDE_CONFIG_DIR` 같은 변수를 설정해 두면 두 조건의 설정이 달라지니 `env | grep -i 'claude\|codex'` 로 먼저 확인합니다.
  - 원격·웹 세션에서는 HOME 에 하네스 설치·CLI 로그인·대상 레포가 없어서 실행할 수 없습니다. 벤치는 로컬 머신에서 돌립니다.
- 에이전트는 PATH의 `claude`/`codex` 바이너리로 실행됩니다(셸 함수·별칭은 적용되지 않음). headroom 같은 래퍼를 거치려면 `--agent-cmd 'headroom wrap claude --'` 또는 환경변수 `KNACK_CLAUDE_CMD`를 씁니다. `knack run`도 같은 환경변수를 따릅니다.
- 비대화 실행에는 CLI 로그인이 필요합니다. `401 authentication_error`가 나면 터미널에서 `claude`(또는 `codex`)를 실행해 로그인한 뒤 다시 시도합니다.
- 모든 옵션: `knack bench --help`, `knack bench ab --help`
- 비대화 모드에서는 설계 게이트에서 멈추므로 벤치 프롬프트에 "설계는 승인된 것으로 보고 진행"처럼 적습니다(`bench/tasks.example.json` 참고).
- Claude는 기본 `--permission-mode acceptEdits`라 셸 명령이 막힐 수 있습니다. 테스트 실행이 필요하면 `--agent-args='--allowedTools Bash'`처럼 넘깁니다.

## 항상 적용되는 공통 규칙
- 주장에는 근거(`path:line`)를 붙이고, 확인하지 못한 것은 `(추정)`으로 표시합니다.
- 완료·통과를 말하기 전에 이번 턴에 검증 명령을 실행하고 출력을 확인합니다. 서브에이전트의 완료 보고도 diff와 테스트로 확인합니다.
- 레포 컨벤션이 우선입니다. 주석은 "왜"에만 달고, 범위 밖 리팩토링은 하지 않습니다.
- 시크릿 값은 출력하지 않고, 운영 환경에는 쓰지 않습니다. 스키마 변경은 마이그레이션 파일로만 합니다.
- 전체 목록: `knack list rules`

## 결과물 위치
대상 레포 안에 만들어지며, 폴더마다 `.gitignore`(`*`)가 있어서 커밋되지 않습니다.
```
.onboarding/   ONBOARDING.md, GLOSSARY.md, QUESTIONS.md, scan.md, flows/
.design/       <날짜>-<slug>/DESIGN.md, SUMMARY.md, REVIEW.md, GATES.md(고위험)
               <날짜>-bug-<slug>/BUGFIX.md
```

## 터미널 명령 `knack`

| 명령 | 설명 |
|---|---|
| `knack list [skills\|rules\|agents\|hooks\|plugins\|mcp] [--all] [--json]` | 하네스 항목과 설치 상태. `--all`이면 외부 스킬·룰·훅·플러그인(Claude Code·데스크톱 앱)·MCP까지 |
| `knack show <skill\|rule\|agent\|hook\|ref\|template\|usage> <이름> [--toc\|--section N\|--path]` | 필요한 부분만 조회 (예: `knack show ref db-migration --section 2`) |
| `knack search <키워드> [-l] [-E]` | 하네스 문서 검색 (`path:line`) |
| `knack doctor` | 구조·중복·설치 상태·환경 점검 |
| `knack add skill <경로\|git URL> [--subdir P] [--name N] [--install]` | 외부 스킬을 하네스에 복사 (출처는 `.knack-source`에 기록) |
| `knack new <skill\|rule\|hook> <이름> [--always]` | 뼈대 생성 (룰은 기본 on-demand, 훅은 기본 꺼짐) |
| `knack adopt skill <이름>` | 에이전트 폴더의 외부 스킬을 하네스로 이동 |
| `knack hook <enable\|disable> <이름>` | 훅 켜기·끄기 (적용은 `knack install`) |
| `knack model [list\|get <작업>\|which "<요청>"\|set …]` | 작업 유형별 모델 조회·분류·변경 |
| `knack run <작업\|auto> [--agent claude\|codex] [--print] -- "<프롬프트>"` | 작업에 맞는 모델로 에이전트 실행 (`--dry-run`: 명령만 출력) |
| `knack gate <status\|run\|reverify> <GATES.md>` | 완료 게이트: 상태만(실행 안 함) · 미충족만 실행 · 전부 재실행. 종료 0 ALL MET · 1 미충족·포기 · 2 형식 오류 |
| `knack persona [show\|init\|set\|import\|check\|enable\|disable\|path]` | 사용자 페르소나 조회·수정 (`persona import -` 로 표준입력) |
| `knack usage [--since 7d] [--by session\|model\|day\|skill\|cwd] [--json]` | 세션 로그 기반 토큰 사용량 집계 |
| `knack bench <init\|ab\|run [--baseline]\|compare\|list\|baseline>` | 작업 세트를 조건별로 실행·비교 (`knack bench --help`) |
| `knack install [--dry-run] [--project <path>] [--agents claude,codex] [--force]` | 설치 (기본값: 글로벌) |
| `knack reinstall [옵션]` | 제거 후 다시 설치. 설치 상태가 꼬였을 때, 또는 다른 클론으로 옮길 때 |
| `knack status` / `knack update` / `knack uninstall` | 상태 / git pull 후 재설치 / 제거 |
| `knack help [스킬]` · `knack scan [경로]` · `knack test` · `knack version` | 사용법 · 레포 스캔 · 스모크 테스트 · 버전 |

## 설치 · 업데이트
```bash
git clone https://github.com/nowgnas/knack.git ~/knack && ~/knack/install.sh --global   # 새 노트북
knack update                                                                              # 업데이트
```
설치하거나 업데이트한 뒤에는 새 에이전트 세션부터 반영됩니다.

### 클론이 여러 개일 때 (하네스 수정용 / 사용자용)

레포를 수정하는 폴더와 사용자로 쓰는 클론을 따로 두어도 됩니다. 설치본은 **마지막으로 `install` 한 클론**을 가리킵니다.

```bash
cd ~/knack && ./install.sh --global     # 이 클론으로 넘겨받기
knack reinstall                         # 꼬였을 때: 제거 후 다시 설치
knack status                            # 어느 클론을 가리키는지 확인
```

- 다른 knack 클론이 만든 링크는 `--force` 없이 교체됩니다(백업도 쌓이지 않습니다). 사용자가 직접 만든 파일·링크는 여전히 `SKIP` 으로 보호됩니다.
- 레포 폴더를 옮기거나 이름을 바꿔 끊어진 하네스 링크도 같은 방식으로 교체됩니다. 이때는 CLI 링크도 끊어져 있으니 새 위치에서 `./install.sh`를 직접 실행하세요.
- `knack status` 는 다른 클론을 가리키는 항목을 `STALE ... (다른 knack 클론을 가리킴)` 으로 보고합니다.
- `knack reinstall --dry-run` 은 아무것도 바꾸지 않습니다. 다만 제거가 실제로 일어나지 않으므로 설치 단계의 예정 건수는 현재 상태 기준으로 적게 나옵니다.
- 수정용 폴더에서 `git pull` 만 하고 사용자용 클론을 설치해 두면, 수정 내용은 반영되지 않습니다. 어느 쪽이 설치돼 있는지는 `knack status` 로 확인하세요.

### harness 에서 개명한 경우

`knack install` 을 한 번 실행하면 개명 전 흔적이 정리됩니다 — 지시 파일의 `harness:start` 블록,
`--harness-hook` 표식 훅, `harness-help`·`harness-manage` 스킬 링크, `~/.local/bin/harness`,
`~/.codex/harness/agents/`. 사용자가 직접 만든 설정·링크는 건드리지 않습니다.

- 셸 설정의 `HARNESS_*` 환경변수는 당분간 그대로 동작합니다(`KNACK_*` 가 우선). 정리하는 편이 좋습니다.
- 벤치 결과는 `~/.harness-bench` 만 있으면 그 폴더를 계속 씁니다. `~/.knack-bench` 로 옮기려면 직접 `mv` 하세요.
- 레포 폴더 이름(`~/harness` → `~/knack`)과 GitHub 레포 이름은 사용자가 직접 바꿉니다. GitHub 은 옛 이름으로도 리다이렉트하므로 기존 remote 는 그대로 동작합니다.
