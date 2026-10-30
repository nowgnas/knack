# knack

백엔드 개발자용 개인 에이전트 하네스입니다. **Claude Code**와 **Codex**의 스킬·룰·훅·서브에이전트를 이 레포 하나에서 관리합니다. **GitHub Copilot CLI**에는 스킬·룰만 연결합니다.
노트북이 바뀌어도 클론한 뒤 `install.sh`를 한 번 실행하면 같은 환경이 됩니다.
개발 절차는 knack 스킬로 통일하고, [superpowers](https://github.com/obra/superpowers)와 [unlazy](https://github.com/Leonxlnx/unlazy)의 검증 규율은 그 안에 흡수했습니다([작업 규율](#작업-규율)).

## 이름의 의미

**knack**은 영어로 "요령, 솜씨, (연습으로 몸에 붙은) 재주"를 뜻합니다(*have a knack for* ~ = ~에 요령이 있다).
에이전트는 매 세션 백지에서 시작하므로, 레포 파악·기능 구현·버그 수정·리뷰처럼 반복되는 일의 요령을 스킬·룰·훅으로 적어 두고 어느 노트북·어느 에이전트에서든 같은 솜씨로 일하게 하자는 뜻입니다.
짧고 입력하기 쉬운 CLI 이름이기도 합니다. 예전 이름은 `harness`였고, 문서에서 "하네스"는 지금도 이 레포(에이전트 설정 묶음)를 가리킵니다.

## 빠른 시작

```bash
git clone https://github.com/nowgnas/knack.git ~/knack
~/knack/install.sh --dry-run    # 무엇이 바뀌는지 확인
~/knack/install.sh              # 글로벌 적용
knack doctor                    # 점검
knack help                      # 사용법
```

`doctor`는 Codex 역할 설정 블록과 기본 모델의 갱신 필요 여부도 확인합니다. Codex 모델 후보가 모두 없으면 설치 시 기존 기본 모델을 유지하고 역할의 모델 지정을 생략합니다. 선택된 모델이 지원하지 않는 effort는 기존 최상위 설정에서도 제거합니다.

## 무엇을 관리하나

| 종류 | 원본 | Claude Code | Codex |
|---|---|---|---|
| 스킬 | `skills/<name>/SKILL.md` | `~/.claude/skills/<name>` 링크 | `~/.agents/skills/<name>` 링크 |
| 서브에이전트 | `agents/*.md` (`task:`) | `~/.claude/agents/*.md` 생성 (`model:` 포함) | `config.toml`의 `[agents.<이름>]` 역할 + `~/.codex/knack/agents/*.toml` |
| 작업 유형별 모델 | `models.json` | 서브에이전트 모델, `settings.json`의 세션 모델 | 역할 모델·effort, `config.toml`의 세션 모델 |
| 룰 (always) | `rules/*.md` | `~/.claude/CLAUDE.md` 블록에 `@import` | `~/.codex/AGENTS.md` 블록에 본문 |
| 룰 (on-demand) | `rules/*.md` | 블록에 이름·시점 한 줄 | 동일 |
| 훅 | `hooks/<name>/hook.json` + 스크립트 | `~/.claude/settings.json`의 `hooks` | `~/.codex/hooks.json` |
| 페르소나 | `persona/core.md` (gitignore) | 지시 블록 맨 앞에 주입 | 동일 |
| CLI | `bin/knack` | `~/.local/bin/knack` 링크 | 동일 |
| 플러그인·MCP | — | 조회만 (`knack list plugins`: Claude Code·데스크톱 앱 플러그인, `knack list mcp`) | 조회만 |

- Copilot CLI(`--agents copilot`, `COPILOT_HOME` 존중): 스킬은 Copilot도 읽는 `~/.agents/skills`를 Codex와 함께 쓰고, always 룰 본문과 on-demand 색인을 `~/.copilot/copilot-instructions.md` 블록에 넣습니다. 서브에이전트·훅·모델은 연결하지 않습니다.
- 기존 설정은 보존합니다. 지시 파일은 `<!-- knack:start -->` 블록만, 훅 파일은 `--knack-hook` 표식이 있는 항목만 관리합니다.
- `harness` 에서 개명했습니다. `knack install` 한 번으로 구 블록·훅·링크가 정리되고, `HARNESS_*` 환경변수는 당분간 함께 동작합니다.
- 레포를 고친 뒤 `knack install`을 잊으면 `knack-stale` 훅이 다음 세션 시작 때 알려 줍니다(생성물만 해당. 스킬은 심링크라 즉시 반영).
- 같은 이름이 이미 있으면 `SKIP`합니다. `--force`를 주면 `~/.knack-backups/<시각>/`에 백업한 뒤 교체합니다.
- 하네스에서 지운 항목의 링크는 다음 설치 때 정리됩니다(`PRUNE`).

## 스킬

| 스킬 | 용도 | 예시 요청 |
|---|---|---|
| `repo-onboarding` | 처음 보는 레포 파악 → `.onboarding/` 문서 | "이 레포 파악해줘" |
| `trace-flow` | 엔드포인트·메시지·배치 흐름 추적, 반대로 테이블·토픽 사용처 역추적 | "POST /api/orders 흐름 따라가줘", "orders 테이블 쓰는 곳 찾아줘" |
| `feature-implementation` | 정책 점검 → 설계 → **승인 후** 구현 → 검증 → 셀프·독립 리뷰 → 결과 기록(`PLAN.md` 한 파일). 고위험이면 완료 게이트 | "주문 취소 API 추가해줘" |
| `bug-fix` | 재현 → 원인 입증 → 수정 계획 → 최소 수정 → 되돌림 확인 → 영향 데이터 점검 | "이 버그 고쳐줘", "이 에러 고쳐줘" + 스택트레이스·로그 |
| `stack-verify` | Spring(Gradle·Maven)·.NET 검증 명령을 근거 파일로 찾아 포맷 → 컴파일 → 단일 테스트 → 전체 테스트 → 마이그레이션(로컬·컨테이너) 순으로 돌리고 결과를 증거로 보고 | "검증 돌려줘", "빌드·테스트 확인해줘" |
| `mistake-proofing` | 같은 실수(커밋되는 `docs/mistakes.md` 원장의 `mistake:<slug>` 2회)를 지시문 대신 테스트·린트·스크립트로 강제하고 과거 실패로 증명해 `docs/enforcement.md`에 기록 | "이 실수 다시 안 나게 해줘", "또 같은 실수야" |
| `verification-skill` | 앱을 로컬에서 띄우고 API를 불러 동작을 증명하는 레포 전용 `verify-<앱>` 스킬을 생성(한 번 실제로 돌려 봐야 증명됨)하거나, 앱 변경을 따라가는지 점검 | "검증 스킬 만들어줘", "verify 스킬 점검해줘" |
| `impl-review` | 구현 맥락이 없는 리뷰어가 요약 대신 코드로 성공 기준을 대조 | "머지 전에 리뷰해줘" |
| `persona` | 자기소개·배경을 에이전트가 쓰는 페르소나(결정 형태)로 정리 | "내 정보 등록해줘" |
| `eli5` | 청중(나이·직무 등)에 맞춘 쉬운 설명. 외부 스킬([DreambigOu/ELI5](https://github.com/DreambigOu/ELI5), MIT)을 그대로 가져옴 | "이거 매니저한테 설명하려면" |
| `ste-explain` | ASD-STE100(통제 영어) 문체 설명. `strict`·`80`·`ko` 세 모드 | "STE로 설명해줘" |
| `knack-manage` | 스킬·룰·훅·서브에이전트·모델 라우팅 관리 | "이 스킬 설치해줘", "하네스 업데이트해줘" |
| `knack-help` | 사용법 안내 ([USAGE.md](skills/knack-help/USAGE.md)) | "하네스 사용법 알려줘" |

## 작업 규율

범용 방법론을 옆에 따로 두면 같은 요청마다 절차가 경쟁하고 토큰도 늘어납니다. 그래서 knack 스킬을 기본 절차로 두고, 외부 스킬·가이드에서 knack에 없던 강점만 가져와 스킬 안에 넣었습니다.
매 세션 로드되는 룰에 들어간 것은 네 항목(검증 증거, 진행·중단 기준, 보고 순서, 사다리)이고, 나머지는 해당 단계에서만 읽는 ref에 있습니다.

| 규율 | 출처 | 적용 위치 |
|---|---|---|
| 완료·통과를 말하기 전에 이번 턴에 검증 명령을 실행하고 출력으로 확인. 서브에이전트 보고도 diff·테스트로 확인 | superpowers `verification-before-completion` | 룰 `core` |
| 성공 기준 테스트는 구현 전에 실패부터 확인 | superpowers `test-driven-development` | `feature-implementation` 6단계 |
| 컴포넌트 경계마다 증거 수집, 잘못된 값의 출처까지 역추적, 가설·변경은 하나씩. 세 번 실패하면 구조 문제로 보고 | superpowers `systematic-debugging` | `bug-fix` 3·5단계 |
| 수정을 되돌리면 재현 테스트가 다시 실패하는지 확인 | superpowers `verification-before-completion` | `bug-fix` 6단계 |
| 리뷰어는 구현자 요약을 믿지 않고 성공 기준을 코드와 한 줄씩 대조. mock만 검증하는 테스트는 커버리지로 치지 않음 | superpowers 스펙 리뷰어(`subagent-driven-development`), `testing-anti-patterns` | `impl-reviewer`, 리뷰 체크리스트 |
| 지적은 코드로 사실인지 확인한 뒤 한 건씩 반영, 틀리면 근거로 반박. 불명확한 지적이 있으면 전부 멈춤 | superpowers `receiving-code-review` | `impl-review` 3단계 |
| 완성도 → 도메인 전문가의 눈 → 결함 사냥 → 정리 순서의 셀프 리뷰 | unlazy 4-pass | `feature-implementation` 8단계 |
| 고위험 변경은 설계 때 `GATES.md` 승인, 보고 직전 전부 재실행, 불가능한 게이트는 인계 | unlazy `GATES.md`·`--reverify`·`ABANDON` | ref `high-risk-gates`, `knack gate` |
| 짜기 전에 사다리를 타고 처음 되는 칸에서 멈춘다. 보안·데이터 유실·권한은 줄이지 않고, 분기·금액·보안 로직은 테스트를 남긴다 | [ponytail](https://github.com/dietrichgebert/ponytail) 사다리 | 룰 `coding`, `feature-implementation` 4단계 |
| 입력이 필요 없으면 멈추지 않고 진행한다. 다음 할 일만 적어두고 끝내지 않는다. 보고는 사용자 결정이 필요한 것을 맨 앞에 | Opus 5.5 활용 가이드 | 룰 `core` |

가져오지 않은 것:
- superpowers의 brainstorming·writing-plans·executing-plans·subagent-driven 개발 흐름 — 정책 점검과 `PLAN.md` 설계 게이트가 같은 역할을 합니다.
- superpowers의 "테스트 없이 짠 코드는 삭제" 규칙과 압박성 문구 — 레거시 백엔드에는 과합니다.
- superpowers의 worktree·브랜치 마무리 — `git-ops` 서브에이전트가 맡습니다.
- unlazy의 Depth Tree·병렬 fan-out — 기능 하나·버그 하나 단위 작업에는 필요 없고 토큰 비용이 큽니다.
- unlazy의 stop 훅(게이트가 열려 있으면 턴 종료 차단) — 완료 선언을 막는 장치는 `knack gate`가 같은 설계(실행 검증, 증거를 게이트 정의 해시에 결속, `reverify`, 포기≠성공)를 이미 갖고 있습니다. 턴 종료를 막는 훅은 훅을 fail-open으로 두는 원칙과 반대라, 게이트를 실제 작업에 써 본 뒤 필요하면 비차단 알림부터 넣습니다.
- ponytail의 `/ponytail-review`·`/ponytail-audit`·`shortcut:` 부채 주석 — 리뷰 스킬이 이미 여럿이고, 부채는 `PLAN.md` 후속 작업이 맡습니다.

두 저장소 모두 MIT 라이선스이며, 개념과 게이트 형식만 가져와 한국어로 다시 썼습니다.

### 완료 게이트 (고위험 변경)

결제·정산, 마이그레이션, 동시성, 메시지 재처리처럼 "테스트 몇 개 통과"로 완료를 판단하기 어려운 변경은 설계 때 `GATES.md`에 관찰 가능한 결과를 명령(`CHECK:`)과 기대 출력(`EXPECT:`)으로 적어 승인받고, 완료 보고 직전에 전부 다시 실행합니다. 규칙은 `knack show ref high-risk-gates`.

```bash
knack gate status .design/<slug>/GATES.md     # 실행 없이 상태·경고
knack gate run .design/<slug>/GATES.md        # 미충족 자동 게이트만 실행, EVIDENCE 기록
knack gate reverify .design/<slug>/GATES.md   # 충족된 것까지 전부 다시 실행 (보고 직전)
```

## 룰·훅·서브에이전트

| 종류 | 이름 | 내용 |
|---|---|---|
| 룰 (always) | `core` | 답변 언어, 영향 범위만큼 읽기, 컨벤션 우선, 근거·검증 증거, 진행·중단 기준, 보고 순서 |
| 룰 (always) | `coding` | 컨벤션·방법론 준수, 가독성, 사다리(안 짜도 되는 길 먼저), 주석 최소화, 범위 준수 |
| 룰 (always) | `backend-safety` | 마이그레이션, 트랜잭션·동시성 알림, 시크릿, 운영 환경 쓰기 금지 |
| 룰 (always) | `knack` | 에이전트 설정은 하네스로 관리, 조회는 knack CLI로 필요한 부분만 |
| 룰 (on-demand) | `git` | 커밋·브랜치·푸시·PR |
| 룰 (on-demand) | `obsidian-daily` | Obsidian 업무 Daily 노트 읽기·작성. 설정은 `~/.config/knack/obsidian-vault.local.yml`(양식: `templates/`) |
| 룰 (on-demand) | `obsidian-ticket` | 티켓 관련 작업 시작 시 브랜치명의 티켓 키로 Obsidian 티켓 노트를 먼저 읽기 |
| 훅 | `guard-agent-config` | 에이전트 설정 폴더에 직접 쓰는(설치·삭제) 명령과 지시·설정 파일의 knack 블록 수정을 막고 knack 명령을 안내 |
| 훅 | `guard-prod-ops` | 운영·원격 DB 대상 마이그레이션(`dotnet ef database update/drop`, Flyway, Liquibase, Gradle·Maven 플러그인)과 운영 환경·프로파일(`ASPNETCORE_ENVIRONMENT`·`SPRING_PROFILES_ACTIVE`=prod 등) 실행을 막음. 판단할 수 없으면 막음(fail-closed) |
| 훅 | `knack-stale` | 설치본이 레포와 다르면 세션 시작 때 알림 (Claude) |
| 서브에이전트 | `impl-reviewer` | 구현 맥락 없는 독립 리뷰 (읽기 전용) |
| 서브에이전트 | `repo-explorer` | 읽기 전용 코드 탐색 |
| 서브에이전트 | `git-ops` | 커밋·푸시·브랜치·PR 위임 |

## 토큰을 아끼는 조회

에이전트가 문서를 통째로 읽지 않도록, 조회는 `lib/knack.py`가 짧게 잘라서 돌려줍니다.

```bash
knack list                                        # 항목과 설치 상태 (한 줄씩)
knack list skills --all                           # 외부·플러그인 스킬까지 → 중복 확인
knack show skill feature-implementation --toc     # 목차와 섹션별 줄 수
knack show skill feature-implementation --section 5
knack show ref db-migration --section "락"
knack search "expand" -l
```

always 룰은 매 세션 로드되므로 짧게 유지합니다. 가끔 필요한 규칙은 on-demand 룰로 두면 지시 파일에는 한 줄 색인만 들어갑니다.

## 관리 명령

```bash
knack add skill https://github.com/owner/repo.git --subdir skills/foo   # 외부 스킬 추가
knack new skill my-skill | new rule team-style | new hook my-hook       # 뼈대 생성
knack adopt skill <이름>                                                # 외부 스킬을 하네스로 이동
knack list plugins                                                      # Claude Code·데스크톱 앱 플러그인
knack model set git haiku --agent claude                                # 작업 유형별 모델 변경 (적용은 knack install)
knack run implement -- "<요청>"                                         # 작업 유형에 맞는 모델로 새 세션 실행
knack hook disable guard-agent-config                                   # 훅 끄기
knack install --dry-run && knack install                                # 적용
```

외부 스킬 제거는 가드 훅이 막습니다. 에이전트가 백업·삭제 명령을 안내하면 사용자가 실행합니다.

## 알려진 한계

- 조회 규율(문서를 `--section`으로 잘라 읽기)은 룰로만 안내합니다. 에이전트가 파일을 통째로 읽어도 막거나 알리지 않습니다. `impl-reviewer`처럼 체크리스트를 통째로 읽는 것이 맞는 경우가 있어 강제하지 않습니다.
- `guard-agent-config`는 판단할 수 없는 입력을 통과시킵니다(fail-open). 명령을 `;`·`&&`·`||`·`|`로 나누고 `cd`를 따라가며 조각마다 판정합니다. 쓰기 여부는 명령 이름(`cp`·`rm`·`tee`·`sed -i` 등)과 리다이렉트 대상으로만 보고, 따옴표 안과 히어독 본문은 데이터로 취급합니다 — 보호 경로를 읽거나 문서에 적는 작업은 막지 않습니다. 대신 경로를 변수에 담거나 스크립트 파일 안에서 쓰는 경우는 보지 못합니다.
- `guard-prod-ops`는 실수 방지 장치이지 보안 경계가 아닙니다. 판단할 수 없는 셸 입력은 막고(fail-closed), 대상 DB는 명령에 명시된 것(`--connection`·`-url=`·`-D…url=`·인라인 환경변수)만 봅니다.
  - 대상 없이 실행하는 마이그레이션은 막고 로컬 대상 명령을 안내합니다. 통과하는 대상: `localhost`·`127.x`·`::1`·`host.docker.internal`·`(localdb)`·`.`, `jdbc:tc:`, 메모리 H2/HSQLDB/Derby, 프로젝트 안의 SQLite 파일, 프로젝트 `.knack/safe-db-hosts`에 한 줄씩 적은 호스트(정확히 일치, 와일드카드 없음). docker-compose 서비스 이름도 여기에 적어야 통과합니다.
  - `knack gate run`·`reverify`의 `CHECK`는 에이전트 셸 도구를 거치지 않으므로, 실행 전에 이 훅을 같은 입력으로 직접 불러 검사합니다(막히면 `guard=deny`로 실패). 여기서는 훅 오류·시간 초과(30초)·해석할 수 없는 출력도 막고, `KNACK_GUARD_PROD` 환경변수는 따르지 않습니다. 끄는 방법은 `knack hook disable guard-prod-ops`(레포 `hook.json`, 즉시 반영) 하나입니다.
  - 운영 환경·프로파일은 대상이 로컬이어도 막습니다. 끄려면 훅 프로세스 환경에 `KNACK_GUARD_PROD=off`를 두거나 `knack hook disable guard-prod-ops`. 명령 앞에 붙인 `KNACK_GUARD_PROD=off`는 무시합니다.
  - 셸 스크립트는 2단계·256KB까지 열어 봅니다(주석 줄 제외). 넘거나 읽을 수 없거나, 같은 명령에서 만든 뒤 실행하면 막습니다. `eval`·`| sh`·명령 자리의 `$VAR`는 위험 단어가 있을 때 막고, `flyway`·`liquibase`·`dotnet ef` 인자 안의 `$( )`는 늘 막습니다. 기록·검색 명령(`gh`·`git`·`echo`…)은 `$( )` 안에 위험 단어가 있을 때만 막습니다. `kubectl exec … -- sh -c 'dotnet ef database update'`처럼 컨테이너 안에서 돌리는 마이그레이션은 `localhost`라도 내 로컬 DB가 아니므로 막습니다.
  - 보지 못하는 것: Makefile·npm scripts·alias, PowerShell `Update-Database`, `appsettings*.json`·`flyway.conf`에만 적힌 대상, localhost로 연 SSH 터널 너머의 운영 DB, 앱 시작 시 자동 마이그레이션(Spring Flyway/Liquibase, EF `Migrate()`), `psql`·`sqlcmd`로 직접 실행하는 DDL. 훅이 시간 초과(10초)로 끝나면 에이전트가 명령을 그대로 실행할 수 있습니다.
- 하네스의 효과(토큰·통과율)는 측정하지 않았습니다. 하네스 안의 A/B 벤치(`knack bench`)와 세션 로그 토큰 집계(`knack usage`)는 측정 결과를 신뢰하기 어려워 제거했습니다. 세션 로그 기반 측정은 하네스 밖의 별도 도구에서 다룹니다.
  - 산출물 축소(`DESIGN`+`SUMMARY`+`REVIEW` → `PLAN` 하나)의 효과도 재지 않았습니다.
  - `repo-onboarding`·`trace-flow`도 실제 레포에서 쓴 적이 없습니다(`.onboarding/`이 생긴 적 없음). 낯선 레포에서 `knack scan` → `repo-onboarding quick`을 한 번 돌려보고 10관점과 `ONBOARDING.md` 분량이 과한지 판단합니다.
  - `knack gate`는 스모크 테스트 밖에서, 즉 실제 작업에서 쓴 적이 없습니다. 고위험 작업에서 한 번 써 비용을 본 뒤에 완료 선언을 기계로 막을지 정합니다(비차단 알림 → 그래도 부족하면 차단형 Stop 훅).

## 구조

```
rules/                  룰 (frontmatter: name, description, load: always|on-demand, when)
skills/<name>/          에이전트 중립 스킬 (SKILL.md + references/ templates/ scripts/)
                        frontmatter overlaps: 는 같은 의도의 외부 스킬 이름 — doctor 가 설치 여부를 확인해 알린다
agents/                 서브에이전트 (frontmatter task: → models.json 의 작업 유형, when: → 위임 조건)
models.json             작업 유형별 모델 라우팅 (티어 → 에이전트별 모델·effort, 세션 기본 모델)
                        모델은 후보 목록도 가능 — 설치된 첫 모델을 쓴다. PC 전용 값은
                        ~/.config/knack/models.local.json (커밋되지 않음)
hooks/<name>/           훅 정의(hook.json)와 스크립트
hooks/_shared/          훅이 함께 쓰는 셸 파서(hook.json 없음 → 설치 대상 아님)
persona/                페르소나 템플릿 (core.md·detail/ 은 gitignore)
templates/              사용자별 설정 양식 (예: obsidian-vault.local.yml.example. 실제 값은 레포 밖에 둠)
lib/knack.py            조회·관리·훅·모델 동기화 (python3 표준 라이브러리)
lib/gate.py             완료 게이트 확인·실행·재검증 (knack gate)
lib/persona.py          페르소나 조회·수정 (knack persona)
bin/knack               CLI
install.sh              설치/상태/제거
tests/smoke.sh          임시 HOME에서 설치·조회·관리·훅·모델 라우팅·게이트 검증
.github/workflows/      push·PR 때 macOS(/bin/bash 3.2)·Ubuntu에서 smoke.sh 실행
AGENTS.md               레포 작업 가이드 (CLAUDE.md 는 이를 import)
CHANGELOG.md            변경 기록 (Unreleased 에 쌓음)
```

## 업데이트 · 제거

```bash
knack update       # git pull + 재설치 + doctor (앞 단계가 실패하면 멈춤)
knack reinstall    # 제거 후 다시 설치 (설치 상태가 꼬였거나 다른 클론으로 옮길 때)
knack uninstall    # 하네스가 만든 링크·블록·훅만 제거
```

레포 폴더를 옮기거나 이름을 바꿨으면 새 위치에서 `./install.sh`를 실행합니다. CLI 링크도 끊어져 있어 `knack install`은 쓸 수 없고, 끊어진 하네스 링크는 설치할 때 자동으로 교체됩니다.
