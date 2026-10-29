---
name: verification-skill
description: 레포의 앱을 사용자처럼 띄우고 호출해 동작을 증명하는 레포 전용 verify-<앱> 스킬을 만들거나 점검한다. "검증 스킬 만들어줘", "verify 스킬 점검해줘"에 사용.
---

# Verification Skill

목적: 빌드·단위 테스트(`stack-verify`)를 넘어, 실제 앱을 띄우고 API를 불러 "기능이 동작한다"를 증거로 남기는 방법을 레포에 스킬로 둔다.
생성물은 사람이 아니라 다음 에이전트가 읽는다. 이 앱을 처음 보는 에이전트가 작업 중간에 바로 따라 할 수 있게 쓴다.
모드는 둘이다: **생성**(스킬이 없을 때), **점검**(있을 때). 정본은 `.agents/skills/verify-<앱>/`, `.claude/skills/verify-<앱>`은 링크다.

## 1. 생성 — 레포에서 먼저 답을 찾는다 (사용자에게는 코드로 알 수 없는 것만)
| 질문 | Spring Boot | .NET |
|---|---|---|
| 표면 | REST 컨트롤러, 메시지 리스너, 배치 | 컨트롤러·Minimal API, 워커, gRPC |
| 띄우기 | `./gradlew bootRun --args='--spring.profiles.active=local'` · `./mvnw spring-boot:run` | `dotnet run --project <Api.csproj> --environment Development` · `launchSettings.json` |
| 의존 자원 | `compose.yaml`·`docker-compose*.yml`, Testcontainers, `application-local.yml` | `docker-compose*.yml`, `appsettings.Development.json`, Aspire AppHost |
| 준비 신호 | `/actuator/health`가 UP, `Started ...Application` 로그 | `Now listening on:` 로그, `/health` |
| 조작 | `curl`, `.http` 파일, 기존 통합 테스트 | `curl`, `.http` 파일, `WebApplicationFactory` 테스트 |
| 관찰 | 응답 본문·상태 코드, 로컬 DB 행, 로그, 발행된 메시지 | 같음 |
| 격리 | 포트·DB 이름을 바꿔 두 벌 띄울 수 있는가 | 같음 |

- 빈 데이터 상태에서 마이그레이션·시드까지 거쳐 "쓸 수 있는 상태"가 되는 것이 준비 완료다. 헬스 체크가 UP이어도 시드가 덜 끝났을 수 있다.
- 로컬·컨테이너 자원만 쓴다. 운영·공유 DB, 운영 프로파일은 쓰지 않는다(`guard-prod-ops` 훅).
- 체크아웃이 그대로 빌드·기동되지 않으면 생성 전에 고치거나 정확히 보고한다. 깨진 상태로 쓴 스킬은 틀린 절차를 가르친다.

## 2. 생성 — 파일 쓰기
1. `templates/verify-SKILL.md` → `.agents/skills/verify-<앱>/SKILL.md`. 자리표시자를 남기지 않고 1절에서 찾은 실제 명령·경로·엔드포인트로 채운다.
2. `templates/feature.md`로 사용자 기능 3~5개를 `features/<기능>.md`에 쓰고 `features/README.md`에 목록을 둔다. 엔드포인트·명령·문서에서 고른다.
3. 도우미 스크립트를 두면 실행 권한을 주고 호출법을 SKILL.md 본문에 적는다.
4. 링크: `python3 <이 스킬 폴더>/scripts/link_skill.py link <레포> verify-<앱>`. 심볼릭 링크를 못 만들면(Windows 권한 등) 복사하고 sha256 목록을 남긴다.

## 3. 생성 — 넘기기 전에 한 번 돌려 본다
생성된 스킬의 지시대로 처음부터 끝까지 한 번 돈다: 띄우기 → 점검 → 기능 하나 조작 → 증거 저장 → 정리 → 정리 뒤에도 증거가 남았는지 확인.
- 실패하면 고치고, 실패한 시도마다 정리 절차도 돌려 프로세스·포트·컨테이너를 남기지 않는다.
- 결과를 `templates/EVIDENCE.md` 형식으로 `.agents/skills/verify-<앱>/EVIDENCE.md`에 적는다. 한 번도 실제로 돌지 않은 스킬은 상태를 **미증명**으로 두고 그렇게 보고한다.
- 대역(로컬 컨테이너로 원격 자원 대체 등)에서 증명했으면, 실제 대상에서 다르게 될 준비 단계를 모두 "미검증"으로 적는다.
- 커밋·PR은 사용자에게 확인받은 뒤에 한다.

## 4. 점검 — 스킬이 앱을 따라가는지
1. 대상 찾기: `.agents/skills/verify-*/`. 여럿이면 묻고, 없으면 생성 모드를 제안한다.
2. 동기화: `link_skill.py check <레포> verify-<앱>`. 링크가 깨졌거나 복사본 sha256이 다르면 표류다.
3. 목록 정리: `features/README.md`와 실제 파일의 누락·중복·죽은 항목.
4. 소스 대조: 기능 파일마다 읽기 전용 서브에이전트(`repo-explorer`)가 "이 기능이 지금 코드에서 어떻게 동작하는가"를 `path:line`으로 답하고, 문서와 다른 곳과 확인 절차 하나를 낸다. 최근 변경에서 목록에 없는 엔드포인트도 경로를 근거로 찾는다.
5. 실제 실행(소스가 깨끗해 보여도 필수): 모든 기능을 한 번 이상 조작한다.
   - 처음, 그리고 조작이 실패한 뒤마다 점검(doctor)을 다시 돌린다. 이상한 상태면 재기동한다.
   - 증거는 정리 뒤에도 정해진 위치에 남는지 확인한다. 이번에 띄운 것은 모두 정리한다.
   - 닿지 못한 기능은 필요한 전제(인증, 외부 시스템)와 시도한 경로를 적어 "도달 불가"로 둔다.
6. 분류: 문서 표류 → 스킬 문서 수정 · 조작 방법 결함 → 스크립트 수정 후 다시 실행해 증명 · 앱 결함 → 사용자에게 보고(제품 코드는 고치지 않는다).
7. 결과를 하나로 말한다: **깨끗함**(수정 없음) / **변경**(증명한 수정만, 사용자 확인 후 커밋) / **막힘**(무엇이 막았는지). `EVIDENCE.md`에 이번 실행 줄을 추가한다.

수정 범위는 verify 스킬 폴더 안뿐이다. 앱 동작이 문서와 다르면 문서를 고칠지(표류) 보고할지(회귀) 먼저 가른다.

<!-- 출처: pstack create-/maintain-verification-skill (MIT, Lauren Tan, cursor/plugins@1ba91fc) · THIRD_PARTY_NOTICES.md -->
