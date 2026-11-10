# knack 사용법

knack 은 백엔드 개발용 개인 에이전트 하네스입니다. 에이전트(Claude Code, Codex)의 **스킬·룰·훅·서브에이전트**를 이 레포 하나에서 관리합니다. GitHub Copilot CLI에는 스킬·룰만 연결합니다.
요청 문장에 맞는 스킬이 자동으로 선택되고, 직접 부를 수도 있습니다.
기본 개발 절차는 knack 스킬(`feature-implementation`, `bug-fix`, `impl-review`)이고, superpowers와 unlazy의 검증 규율을 이 안에 흡수했습니다. 무엇을 어디서 가져왔는지는 README의 "작업 규율"에 있습니다.

- **Claude Code**: `/스킬이름` (예: `/repo-onboarding quick`)
- **Codex**: 프롬프트에 `$스킬이름`으로 언급하거나 `/skills`에서 선택

## 상황별 사용법

| 상황 | 이렇게 요청 | 스킬 | 결과물 |
|---|---|---|---|
| 처음 보는 레포 | "이 레포 파악해줘", "quick으로 온보딩", "deep 모드로 결제 도메인 위주로" | `repo-onboarding` | `.onboarding/ONBOARDING.md` 외 |
| API 동작 이해 | "POST /api/orders 흐름 따라가줘" | `trace-flow` | `.onboarding/flows/*.md` |
| 자원 사용처 찾기 | "orders 테이블 쓰는 곳 전부 찾아줘" | `trace-flow` (역방향) | `.onboarding/usages/*.md` |
| 새 기능 | "주문 취소 API 추가해줘" (요구사항·정책 문서가 있으면 함께) | `feature-implementation` | 경량은 없음 · 표준은 `.design/<slug>/PLAN.md` |
| 버그 | "이 버그 고쳐줘", "이 에러 고쳐줘" + 스택트레이스·로그 | `bug-fix` | 경량은 `BUGFIX.md` 없음 · 그 밖에는 `.design/bug-<slug>/BUGFIX.md` · 실수 종류가 분명하면 레포의 `docs/mistakes.md` 한 줄(커밋) |
| 빌드·테스트 검증 | "검증 돌려줘", "빌드·테스트 확인해줘" | `stack-verify` | 대화 보고(명령별 결과) |
| 실수 재발 방지 | "이 실수 다시 안 나게 해줘" | `mistake-proofing` | `docs/mistakes.md`(발생 원장) · `docs/enforcement.md` |
| 앱 동작 검증 스킬 | "검증 스킬 만들어줘", "verify 스킬 점검해줘" | `verification-skill` | `.agents/skills/verify-<앱>/`(+ `.claude/skills/` 링크), `EVIDENCE.md` |
| 머지 전 리뷰 | "머지 전에 리뷰해줘" | `impl-review` | 대화 보고 · 고위험만 `.design/<slug>/REVIEW.md` |
| 스킬·룰·훅 설치·관리 | "이 스킬 설치해줘", "훅 추가해줘", "하네스 업데이트해줘" | `knack-manage` | 하네스 레포 변경 |
| 내 정보 등록 | "내 정보 등록해줘", "페르소나 수정해줘" (자기소개 파일이 있으면 함께) | `persona` | `persona/core.md`, `persona/detail/*.md` |
| 쉬운 말로 설명 | "이거 매니저한테 설명하려면", "ELI5로 설명해줘" | `eli5` | — |
| 모호함 없는 설명 | "STE로 설명해줘", "ASD-STE100 80%로 써줘" | `ste-explain` | — |
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

### trace-flow — 흐름 추적과 사용처 역추적
- 정방향 입력: `METHOD /path`, 토픽·큐 이름, 배치 잡, `Class.method`
  - 출력: 시퀀스 다이어그램, 단계별 표(`path:line`), 데이터 변경, 부수효과, 실패 경로
- 역방향 입력: 테이블·컬럼, 토픽·큐, 캐시 키, 설정 키 — "orders 테이블 쓰는 곳 전부 찾아줘"
  - 출력: 읽는 곳과 쓰는 곳을 나눈 표(`path:line` + 진입점까지의 호출 경로), 코드 밖 접근(배치·마이그레이션·뷰), **누락 가능성과 확인 범위**, 스키마 변경 시 영향
  - 스키마 변경·데이터 보정 전에 먼저 돌립니다. "전부 찾았다"는 주장에는 어디까지 확인했는지가 함께 있어야 합니다.

### feature-implementation — 기능 구현
```
요구사항 정리 → 정책 점검(✅/❓/⚠️) → 컨벤션 파악 → 구현 설계 (+ 고위험이면 GATES.md)
  → [게이트] 질문 해소 + 설계 승인 + 테스트 계획 합의 (+ 고위험이면 게이트 명령 승인)
  → 구현 (성공 기준 테스트의 실패를 먼저 확인) → 검증 (고위험이면 knack gate run)
  → 셀프 리뷰 4단계 → 독립 리뷰 → 보고 직전 knack gate reverify (고위험) → 핵심 구현 요약
```
- 게이트를 통과하기 전에는 코드를 수정하지 않습니다. 설계가 괜찮으면 "진행해"처럼 **명시적으로 승인**해 주세요.
- 승인 뒤에는 로컬 빌드·테스트·린트 실행과 실패 수정을 묻지 않고, 완료 기준(테스트·린트 통과, 독립 리뷰 반영, 결과 기록)까지 진행한 다음 한 번 보고합니다.
- 모듈 2개 이하이고 정책·데이터 모델·API 계약이 그대로면 경량 모드입니다 — 계획을 대화로 확인받고 파일은 만들지 않습니다. 모듈 3개 이상이거나 계약이 바뀌면 `PLAN.md` 한 개를 만들고 구현 결과도 그 파일에 덧붙입니다. "설계 없이 바로 해줘"라고 하면 게이트를 건너뜁니다(가정은 보고에 남음).
- 스키마가 바뀌면 DB 마이그레이션 가이드(expand → contract, 락, 롤백)가 설계에 적용됩니다.
- 성공 기준 테스트는 구현 전에 실패하는 것부터 확인하고(Red → Green), 리뷰 전에 완성도 → 도메인 전문가의 눈 → 결함 사냥 → 정리 순서로 셀프 리뷰합니다.
- **고위험 변경**(스키마·데이터 보정, 금액·결제·정산, 동시성·멱등성, 메시지 재처리, 대규모 리팩터링)은 설계 때 완료 게이트 `GATES.md`를 함께 승인받고, 완료 보고 직전에 `knack gate reverify`로 전부 다시 확인합니다. 규칙: `knack show ref high-risk-gates`

### bug-fix — 버그 수정
- 원인을 입증하기 전에는 고치지 않습니다. 재현 테스트를 먼저 만듭니다.
- 동작·정책 변경, API·스키마 변경, 데이터 보정, 3개 파일 초과, 추정 수정 중 하나라도 해당하면 승인 후 수정합니다.
- 잘못 저장된 데이터가 있으면 조회 쿼리와 보정 스크립트 **초안**만 만듭니다. 실행은 사람이 합니다.
- 가설은 한 번에 하나씩, 여러 컴포넌트를 거치면 경계마다 증거를 모읍니다. 수정을 되돌리면 재현 테스트가 다시 실패하는지까지 확인합니다.
- 수정 시도가 세 번 실패하면 네 번째 수정 대신 구조 문제로 보고 방향을 정합니다. 고위험 영역이면 기능 구현과 같은 완료 게이트를 씁니다.

### stack-verify — 스택별 검증 명령
- `scripts/detect.py`가 Gradle·Maven·.NET 빌드 단위와 명령(포맷·컴파일·단일 테스트·전체 테스트·마이그레이션 도구)을 JSON으로 낸다. 근거 없는 명령은 만들지 않는다
- 순서: 포맷 → 컴파일 → 단일 테스트 → 영향 테스트 → 린트 → 마이그레이션(로컬·Testcontainers만) → 머지 직전 전체 빌드
- 돌리지 못한 단계는 "안 함"과 이유를 보고한다
- CI가 운영 프로파일·환경으로 돌리는 명령은 로컬 프로파일로 바꿔 돌리고 바꾼 점을 보고합니다
- 레포에 `verify-<앱>` 스킬도 있으면 `stack-verify`(빌드·테스트)를 먼저, 통과한 뒤 `verify-<앱>`(띄워서 동작 확인)을 돌립니다

### mistake-proofing — 같은 실수를 구조로 막기
- `bug-fix`가 레포의 `docs/mistakes.md`(커밋되는 원장)에 `mistake:<slug>`를 한 줄씩 추가하고, 같은 태그가 두 번 나오면 대상입니다. `scripts/mistakes.py list|check <레포>`로 판정합니다. 원장이 커밋되므로 어느 PC·clone에서 세어도 같은 횟수입니다(CI에서 돌리려면 CI가 knack 레포도 체크아웃). `.design/`의 `BUGFIX.md`는 세지 않고, 원장으로 옮겼다는 표시가 없는 `BUGFIX.md`의 태그는 "참고:"로 이전을 알립니다. `#12`·`PR #12`는 원장에서 12번 링크가 한 레포뿐이면 그 링크와 같은 기록으로 셉니다.
- 타입·아키텍처 테스트(ArchUnit, NetArchTest)·분석기·테스트·CI 순으로 강제 수단을 고르고, 실패가 있던 코드에서 실제로 실패하는지 증명합니다(과거 커밋은 `git worktree add`로 따로 꺼냄). "강제 불가"는 실제 이유를 적어야 인정됩니다.
- `docs/enforcement.md`에 태그·룰·강제 수단·실행 명령·과거 실패 증명을 적고, 같은 내용의 지시문은 사용자 확인 후 지웁니다.

### verification-skill — 레포 전용 동작 검증 스킬
- 생성: 레포에서 띄우기·준비 신호·조작·관찰 방법을 찾아 `verify-<앱>` 스킬과 기능 목록(`features/`)을 쓰고, 한 번 처음부터 끝까지 돌려 `EVIDENCE.md`에 기록합니다. 기록이 없으면 "미증명"입니다.
- 점검: 링크·복사본 동기화(`scripts/link_skill.py check`), 기능별 소스 대조, 모든 기능 실제 실행 후 깨끗함·변경·막힘 중 하나로 보고합니다. 제품 코드는 고치지 않습니다.
- 로컬·컨테이너 자원만 씁니다.

### impl-review — 독립 리뷰
- 구현 맥락이 없는 리뷰어가 diff를 설계 문서, 레퍼런스 기능, 체크리스트와 대조합니다.
  - Claude: `impl-reviewer` 서브에이전트
  - Codex: `codex exec -s read-only` 새 세션
- 심각도는 🔴 Blocker · 🟠 Major · 🟡 Minor · ⚪ Nit · ❔ 질문 다섯 단계입니다. 🔴·🟠는 반영하고, 리뷰는 최대 2라운드까지 합니다.
- 돌려 보지 못한 동작 지적은 **❔ 잠재 🔴/🟠**와 판가름할 명령(증명 요청)으로 옵니다. 실행해 결함이면 🟠로 반영하고, 안전하게 돌릴 명령이 없으면 사용자가 정합니다. 잠재 🔴/🟠가 남아 있으면 완료로 보고하지 않습니다.
- 리뷰어는 구현자의 요약을 믿지 않고 성공 기준을 코드와 한 줄씩 대조합니다. 구현자는 지적을 반영하기 전에 코드로 사실인지 확인하고, 틀리면 근거를 들어 반박합니다.

### knack-manage — 스킬·룰·훅 관리
- 스킬을 설치할 때 에이전트 폴더에 바로 넣지 않고 하네스에 추가한 뒤 `knack install`로 연결합니다.
- `knack add skill`은 스킬 폴더 밖을 가리키는 링크, 절대 링크, 끊어진 링크를 거부합니다. 폴더 안을 가리키는 상대 링크는 유지합니다.
- 설치 전에 `knack list --all`로 하네스와 외부에 이미 있는 스킬(같은 이름, 플러그인 스킬 포함)을 확인합니다.
- 선택 훅 `guard-agent-config`를 켜면 에이전트 폴더에 직접 설치하는 작업을 막습니다. 기본값은 꺼짐입니다.
- 외부 스킬·플러그인은 `knack list --all`로 봅니다. 데스크톱 앱(Cowork)에서 설치한 플러그인과 앱 기본 제공 스킬도 포함되며, 이들은 앱 설정에서 켜고 끕니다.
- 외부 스킬 제거 전에는 대상과 백업을 확인합니다.

### eli5 — 청중에 맞춘 설명 (외부 스킬)
- 출처: [DreambigOu/ELI5](https://github.com/DreambigOu/ELI5) (MIT). `knack add skill`로 가져왔습니다. description 은 하네스 기준(160자)에 맞춰 줄였고 본문은 원본 그대로입니다.
- 청중을 나이·학년·직무·관계 중 하나로 잡고 어휘·비유·톤·깊이를 맞춥니다. 청중을 안 적으면 "5살"이 기본입니다.
- 설명 구조: 한 줄 정의 → 비유 → 청중 수준에 맞는 세부 → "그래서 나한테 뭐가 달라지나".
- 코드·에러 메시지도 대상입니다. 먼저 원본을 읽고 목적부터, 그다음 동작 순서로 설명합니다.
- 결과는 채팅 답변입니다. 파일(HTML 등)은 만들지 않습니다.

### ste-explain — ASD-STE100 문체 설명
- Karpathy가 제안한 "ASD-STE100으로 설명해줘"(항공 정비 매뉴얼용 통제 영어)를 스킬로 만든 것입니다. 비유 없이 사실·절차만 짧은 능동문으로 씁니다.
- 모드: `strict`(영어, 승인 어휘까지 지킴) / `80`(영어, 핵심 규칙만 — Karpathy의 "80% of the way") / `ko`(한국어, STE 원칙만 옮긴 STE식 문체). 모드를 안 적으면 한국어 대화는 `ko`, 영어 대화는 `80`입니다.
- 구조: 무엇 → 왜 → 동작/절차 → 주의. 답변 첫 줄에 `[STE: 모드]`를 표시합니다.
- 규칙 세부·전후 예시: `knack show ref ste-rules`. 규격 원문·사전은 저작권 때문에 넣지 않았습니다.
- 청중에 맞춘 비유가 필요하면 `eli5`를 씁니다.

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
- 증거와 해시는 같은 파일에서 수정할 수 있어 실행 사실의 위조를 막지 못합니다. 기존 증거를 신뢰할 수 없으면 `reverify`로 다시 실행하세요. 린트 경고를 종료 코드에 반영하려면 `--strict`를 씁니다.
- 규칙 전체: `knack show ref high-risk-gates` · 템플릿: `knack show template GATES`

## 룰과 훅

| 종류 | 위치 | 적용 방식 |
|---|---|---|
| always 룰 | `rules/*.md` (`load: always`) | Claude: `CLAUDE.md`에 import / Codex: `AGENTS.md`에 본문 블록. 매 세션 로드되므로 짧게 유지 |
| on-demand 룰 | `rules/*.md` (`load: on-demand`, `when:`) | 지시 파일에는 이름과 시점 한 줄만 들어가고, 본문은 필요할 때 `knack show rule <이름>`으로 읽음 |
| 훅 | `hooks/<이름>/hook.json` + 스크립트 | `settings.json`(Claude), `hooks.json`(Codex)에 `--knack-hook` 표식이 붙은 항목만 추가·제거. 다른 훅은 건드리지 않음 |

선택 훅 `guard-agent-config` (기본 꺼짐)는 `~/.claude/skills`, `~/.agents/skills`, `~/.codex/skills`, `~/.claude/agents`에 직접 쓰는 것과, 지시·설정 파일(`CLAUDE.md`·`AGENTS.md`·`config.toml`)의 `knack:start … knack:end` 블록을 고치는 편집을 막습니다. 하네스로 이어지는 링크를 통한 수정, 블록 밖 편집, 보호 경로 읽기는 허용합니다. 끄려면 `knack hook disable guard-agent-config` → `knack install`.

선택 훅 `guard-prod-ops` (기본 꺼짐)(Claude·Codex `PreToolUse`)는 운영·원격 DB 대상 마이그레이션(`dotnet ef database update/drop`, Flyway, Liquibase, Gradle·Maven 플러그인)과 운영 환경·프로파일(`ASPNETCORE_ENVIRONMENT`·`SPRING_PROFILES_ACTIVE`=prod 등) 실행을 막습니다. 다른 훅과 달리 판단할 수 없으면 막습니다(fail-closed). 통과하는 대상은 localhost·Testcontainers·메모리 DB·프로젝트 SQLite 파일과 프로젝트 `.knack/safe-db-hosts`에 한 줄씩 적은 호스트입니다. `knack gate run`·`reverify`의 `CHECK`에는 적용되지 않습니다. 훅을 켜거나 끄려면 `knack hook enable|disable guard-prod-ops` → `knack install`.

기본 훅 `knack-stale`(Claude `SessionStart`)은 설치본이 레포와 다르면 세션 시작 때 알립니다. 스킬은 심링크라 레포를 고치면 바로 반영되지만 룰 블록·서브에이전트·훅·모델은 `install.sh`가 만드는 생성물이라 레포만 고치면 낡은 상태로 남기 때문입니다. 판단은 `install.sh --status`가 하고, 훅은 알리기만 합니다(설치는 사용자 승인 후 `knack install`). 끄려면 `knack hook disable knack-stale` → `knack install`.

## 작업 유형별 모델

`models.json`이 작업 유형(설계·구현·리뷰·탐색·git·문서·조회)마다 쓸 모델을 정합니다. 작업은 티어(deep / standard / fast)에 묶이고, 티어는 에이전트별 모델로 이어집니다. 현재 표는 `knack model`로 확인합니다.

| 적용 방식 | Claude Code | Codex |
|---|---|---|
| 위임 서브에이전트 (`agents/*.md`의 `task:`) | `~/.claude/agents/*.md`를 `model:`을 넣어 생성 | `~/.codex/config.toml`에 `[agents.<이름>]` 역할, `~/.codex/knack/agents/*.toml`에 모델·effort |
| 세션 기본 모델 (`main`) | `~/.claude/settings.json`의 `model` | `~/.codex/config.toml`의 `model`, `model_reasoning_effort` |
| 지시 파일 블록 | "커밋·푸시·PR → `git-ops`에 위임" 같은 색인 몇 줄 | 동일 (`spawn_agent`로 위임) |

전역 설치는 세션 기본 모델을 유지합니다. `knack install --with-main`을 쓰면 위 설정을 `main` 값으로 갱신합니다. 먼저 `--with-main --dry-run`으로 확인하세요.

- 커밋·푸시·PR은 `git-ops`, 탐색은 `repo-explorer`, 독립 리뷰는 `impl-reviewer`에 위임되고, 설계·구현은 세션 모델로 진행합니다.
- 스크립트로 고르기: `knack model get <작업> --agent codex --format flags`, `knack run <작업> -- "<요청>"`(작업 유형에 맞는 모델로 새 세션 실행). 작업 유형은 `knack model list`로 확인합니다.
- Claude·Codex 비대화 실행에서 프롬프트를 인자에 노출하지 않으려면 `knack run implement --agent claude --print --prompt-file <파일>` 또는 `--prompt-file -`로 표준입력을 사용합니다. 인자로 넘긴 프롬프트는 `knack run`을 호출할 때 노출될 수 있습니다. 대화형 실행의 초기 프롬프트는 에이전트에 인자로 전달되므로 민감한 내용은 실행 후 직접 입력하세요.
- 바꾸기: `knack model set git haiku --agent claude`, `knack model set implement deep` → `knack install`. 세션 기본 모델은 `knack model set main deep --agent codex` → `knack install --with-main`.
- **PC마다 설치된 모델이 다를 때**: 모델을 후보 목록으로 적으면(`knack model set tier:deep "gpt-6-astra,gpt-6-sol" --agent codex --effort high`) 설치된 첫 모델을 씁니다. Codex는 `~/.codex/models_cache.json`으로 설치 여부를 확인하고, 지원하지 않는 effort는 떨굽니다. Claude 별칭(`opus`·`sonnet`·`haiku`)은 CLI가 풀어 주므로 확인 대상이 아닙니다.
- 후보가 전부 없으면 `knack run`은 모델 플래그 없이 CLI 기본값으로 실행하고 알립니다. `knack doctor`도 경고합니다.
- `knack run`의 에이전트는 PATH의 `claude`/`codex` 바이너리로 실행됩니다(셸 함수·별칭은 적용되지 않음). headroom 같은 래퍼를 거치려면 환경변수 `KNACK_CLAUDE_CMD`(예: `'headroom wrap claude --'`)를 씁니다.
- 비대화 실행에는 CLI 로그인이 필요합니다. `401 authentication_error`가 나면 터미널에서 `claude`(또는 `codex`)를 실행해 로그인한 뒤 다시 시도합니다.
- 이 PC에만 적용할 값은 `~/.config/knack/models.local.json`에 같은 구조로 적습니다. `models.json` 위에 덮어쓰며 커밋되지 않고, `knack model set`은 이 파일을 건드리지 않습니다.

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

## 항상 적용되는 공통 규칙
- 주장에는 근거(`path:line`)를 붙이고, 확인하지 못한 것은 `(추정)`으로 표시합니다.
- 완료·통과를 말하기 전에 이번 턴에 검증 명령을 실행하고 출력을 확인합니다. 서브에이전트의 완료 보고도 diff와 테스트로 확인합니다.
- 레포 컨벤션이 우선입니다. 주석은 "왜"에만 달고, 범위 밖 리팩토링은 하지 않습니다.
- 시크릿 값은 출력하지 않고, 운영 환경에는 쓰지 않습니다. 스키마 변경은 마이그레이션 파일로만 합니다.
- 전체 목록: `knack list rules`

## 결과물 위치
대상 레포 안에 만들어지며, 폴더마다 `.gitignore`(`*`)가 있어서 커밋되지 않습니다.
`.design/`는 **메인 worktree** 한 곳에만 둡니다(`knack work path`). 커밋되지 않는 파일은 worktree마다 따로라서, 각 worktree에 만들면 다른 세션·에이전트가 볼 수 없기 때문입니다.
```
.onboarding/   ONBOARDING.md, GLOSSARY.md, QUESTIONS.md, scan.md, flows/
.design/       <slug>/PLAN.md — 요구사항·정책·설계·결정 이력(8절)·결과와 리뷰(9절)를 한 파일에 (표준 규모부터)
               <slug>/PROGRESS.md — 진행 기록 (`knack work log`가 한 줄씩 덧붙임)
               <slug>/GATES.md, REVIEW.md — 고위험일 때만
               bug-<slug>/BUGFIX.md
```
| 무엇을 찾나 | 어디 |
|---|---|
| 설계·정책 판정·열린 질문 | `PLAN.md` 1~7절 |
| 의사결정(대안·이유·결정한 사람) | `PLAN.md` 8절, 버그는 `BUGFIX.md` 가설 기록·수정 표 |
| 구현 진행·승인 시점·막힘·인계 | `PROGRESS.md` (`knack work status <slug>`) + `PLAN.md` 7절 체크박스 |
| 검증·리뷰 결과 | `PLAN.md` 9절, 고위험은 `GATES.md`(증거)·`REVIEW.md`(지적 전문) |
| 티켓 배경·파악·대안과 결정의 이유·최종 결과·배포 상태 | Obsidian `{Work}/{티켓키}-{과제명}/` (`obsidian-ticket` 룰), 팀 공유는 PR 설명 |

`.design/`과 Obsidian은 독자와 수명으로 나눕니다. `.design/`은 작업 중인 에이전트가 읽고 머지되면 끝나는 실행 문서(변경 파일·구현 순서·증거·진행 기록), Obsidian은 사람이 나중에 읽는 지식입니다. 시작할 때는 노트를 읽고 `PLAN.md`에 요약과 경로만, 진행 중 상태는 `.design/`에만, 끝날 때 결론만 `구현.md`로 옮깁니다.

예외로 레포에 커밋하는 것: `docs/mistakes.md`(실수 발생 원장)·`docs/enforcement.md`(`mistake-proofing`), `.agents/skills/verify-<앱>/`(`verification-skill`).

## 여러 에이전트가 같은 과제를 할 때
대화는 세션마다 따로라서, 상태는 과제 문서로만 맞춥니다.
```bash
knack work list                                   # 과제 목록 · 상태 · 구현 순서 n/m · 작업 중인 에이전트
knack work status ORDER-123-cancel                # 설계 승인 기록 · 남은 구현 순서 · 작업 중 · 최근 기록
knack work path ORDER-123-cancel                  # 문서 폴더 (없으면 만든다, 어느 worktree에서나 같은 경로)
knack work log ORDER-123-cancel 시작 "재고 복원" --step 7-2   # 사건: 시작·완료·막힘·인계·승인·결정·메모
```
- 이어받는 에이전트는 `status`와 `PLAN.md`부터 읽습니다. 승인 기록이 없으면 구현 전에 다시 확인합니다.
- 기본 훅 `knack-work`(Claude `SessionStart`)가 최근 30일 안에 손댄, 끝나지 않은 과제를 세션 시작 때 알려 줍니다. 상태가 `완료`인 과제와 과제 문서가 없는 레포에서는 조용합니다. 끄려면 `knack hook disable knack-work`. Codex는 지시 블록의 룰 한 줄로만 안내됩니다.
- 같은 단계를 다른 에이전트가 `시작`하고 닫지 않았으면 `log 시작`이 경고합니다(막지는 않습니다). 닫는 사건은 `완료`·`막힘`·`인계`입니다.
- 기록의 `누가`는 `<에이전트>#<세션 ID 앞 4자>@<worktree>:<브랜치>`입니다(세션 ID는 Claude Code와, 환경변수로 알려 주는 Codex에서만 붙습니다). 이름을 직접 정하려면 `--who`나 `KNACK_AGENT`를 씁니다.
- `시작`만 있고 하루 넘게 닫히지 않은 기록은 "끊긴 세션일 수 있다"로 표시합니다. 사용자에게 확인하고 `인계`로 닫습니다.
- 공유 범위는 **이 PC의 같은 레포 worktree**입니다. 다른 clone·PC와 나누려면 레포에서 한 번 `git config knack.workdir <공유 폴더>`를 실행합니다(모든 worktree에 적용, 세션마다 지정할 필요 없음). 한 번만 바꾸려면 `KNACK_WORK_DIR`.
- **Codex 샌드박스**: Codex의 `workspace-write`는 현재 worktree 밖에 쓰지 못합니다. `knack run … --agent codex`는 과제 문서 폴더가 밖에 있으면 `--add-dir <폴더>`를 자동으로 붙입니다. Codex를 직접 띄울 때는 `codex --add-dir "$(knack work path)"`. 그 폴더만 열리고 나머지 제한은 그대로입니다.
- 그래도 쓰지 못해 worktree 안에 기록됐으면(경고가 나옵니다) 쓸 수 있는 세션에서 `knack work sync [slug]`로 합칩니다. 진행 기록은 없는 줄만 덧붙이고, 내용이 다른 파일은 덮어쓰지 않고 충돌로 알립니다(종료 1).
- `knack gate`를 다른 worktree에서 부르면 문서가 있는 메인 worktree가 아니라 그 worktree의 코드를 검증하고, EVIDENCE에 `commit=`을 남깁니다.

## 터미널 명령 `knack`

| 명령 | 설명 |
|---|---|
| `knack list [skills\|rules\|agents\|hooks\|plugins\|mcp] [--all] [--json]` | 하네스 항목과 설치 상태. `--all`이면 외부 스킬·룰·훅·플러그인(Claude Code·데스크톱 앱)·MCP까지 |
| `knack show <skill\|rule\|agent\|hook\|ref\|template\|usage> <이름> [--toc\|--section N\|--path]` | 필요한 부분만 조회 (예: `knack show ref db-migration --section 2`) |
| `knack search <키워드> [-l] [-E]` | 하네스 문서 검색 (`path:line`) |
| `knack doctor` | 구조·중복(같은 이름 + `overlaps:`로 선언한 기능 중복)·설치 상태·환경 점검 |
| `knack add skill <경로\|git URL> [--subdir P] [--name N]` | 외부 스킬을 하네스에 복사 (출처는 `.knack-source`에 기록) |
| `knack new <skill\|rule\|hook> <이름> [--always]` | 뼈대 생성 (룰은 기본 on-demand, 훅은 기본 꺼짐) |
| `knack adopt skill <이름>` | 에이전트 폴더의 외부 스킬을 하네스로 이동 |
| `knack hook <enable\|disable> <이름>` | 훅 켜기·끄기 (적용은 `knack install`) |
| `knack model [list\|get <작업>\|set …]` | 작업 유형별 모델 조회·변경 |
| `knack run <작업\|main> [--agent claude\|codex] [--print] -- "<프롬프트>"` | 작업에 맞는 모델로 에이전트 실행 (`--dry-run`: 명령만 출력) |
| `knack gate <status\|run\|reverify> <GATES.md>` | 완료 게이트: 상태만(실행 안 함) · 미충족만 실행 · 전부 재실행. 종료 0 ALL MET · 1 미충족·포기 · 2 형식 오류 |
| `knack work <list\|status [slug]\|path [slug]\|log <slug> <사건> "<메모>" [--step S]\|sync [slug]>` | 과제 문서 위치(메인 worktree의 `.design/`)와 진행 기록 |
| `knack persona [show\|init\|set\|import\|check\|enable\|disable\|path]` | 사용자 페르소나 조회·수정 (`persona import -` 로 표준입력) |
| `knack install [--dry-run] [--project <path>] [--agents claude,codex] [--force] [--with-main]` | 설치 (기본값: 글로벌, 세션 모델 유지) |
| `knack reinstall [옵션]` | 제거 후 다시 설치. 설치 상태가 꼬였을 때, 또는 다른 클론으로 옮길 때 |
| `knack status` / `knack update` / `knack uninstall` | 상태 / git pull → 재설치 → doctor / 제거 |
| `knack help [스킬]` · `knack scan [경로]` · `knack test` · `knack version` | 사용법 · 레포 스캔 · 스모크 테스트 · 버전 |

## 설치 · 업데이트

Codex 모델 후보가 모두 없으면 서브에이전트 역할의 모델 지정을 생략합니다. `--with-main` 사용 시 후보가 모두 없으면 기존 기본 모델을 유지하고, 선택된 모델이 지원하지 않는 effort는 기존 최상위 설정에서도 제거합니다. `knack doctor`는 역할 설정 블록의 갱신 필요 여부를 확인합니다.

```bash
git clone https://github.com/nowgnas/knack.git ~/knack && ~/knack/install.sh --global   # 새 노트북
knack update                                                                              # 업데이트 (pull → 설치 → doctor)
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
- 레포 폴더 이름(`~/harness` → `~/knack`)과 GitHub 레포 이름은 사용자가 직접 바꿉니다. GitHub 은 옛 이름으로도 리다이렉트하므로 기존 remote 는 그대로 동작합니다.
