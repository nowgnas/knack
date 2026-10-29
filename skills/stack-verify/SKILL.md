---
name: stack-verify
description: Spring(Gradle·Maven)·.NET 레포의 빌드·테스트·포맷·마이그레이션 검증 명령을 근거 파일로 찾아 실행하고 결과를 증거로 보고한다. "검증 돌려줘", "빌드·테스트 확인해줘"에 사용.
---

# Stack Verify

목적: "됐다"를 말하기 전에, 이 레포에서 실제로 통하는 검증 명령을 찾아 돌리고 결과를 증거로 남긴다.
명령은 추측하지 않는다. 근거 파일(빌드 파일, 래퍼, 솔루션, CI 설정)에서 찾은 명령만 쓴다.

## 1. 명령 찾기
```bash
python3 scripts/detect.py <레포 경로>   # 이 스킬 폴더 기준 경로
```
JSON(`schema_version` 1)을 읽는다.

| 필드 | 뜻 |
|---|---|
| `units[]` | 빌드 단위. `kind`(gradle·maven·dotnet), `run_dir`(명령을 돌릴 폴더), `evidence`(근거 파일) |
| `commands` | `compile`·`test`·`single_test`·`format`·`lint`·`full`. 근거가 없으면 `null` |
| `migration` | `tool`(flyway·liquibase·ef-core), 근거, `testcontainers` 사용 여부 |
| `ci_files` | CI 설정. CI가 다른 명령(프로파일, 플래그)을 쓰면 CI 쪽을 따른다 |

- 단위가 여럿이면 바꾼 파일이 속한 `run_dir`만 돌린다.
- `null`인 명령은 만들어 내지 않는다. README·CI에서 찾고, 없으면 "검증 명령 없음"으로 보고한다.
- 래퍼(`./gradlew`, `./mvnw`)가 있으면 늘 래퍼를 쓴다. 전역 `gradle`·`mvn`은 버전이 다를 수 있다.

## 2. 돌리는 순서 (빠른 실패부터)
1. `format.check` → 실패하면 `format.apply` 후 diff를 보여 주고 다시 check
2. `compile`
3. `single_test`: 새로 쓰거나 고친 테스트 클래스만. 실패 테스트가 먼저 빨간색인지 확인(버그 수정이면 고치기 전 실패 증거)
4. `test`: 영향 범위 테스트 전체
5. `lint`(있으면)
6. 마이그레이션을 바꿨으면 3절
7. 머지 직전이면 `full`

실패하면 멈추고 원인을 고친다. 같은 명령을 고치지 않고 다시 돌려서 통과시키지 않는다(불안정 테스트면 그렇다고 보고).

## 3. 마이그레이션 검증 (로컬·컨테이너 DB만)
운영·공유 DB에 연결하는 명령은 돌리지 않는다. `guard-prod-ops` 훅이 막으면 우회하지 말고 사용자에게 명령만 제안한다.

| 도구 | 적용 확인 | 되돌리기 확인 |
|---|---|---|
| Flyway | 빈 DB에 처음부터 적용(Testcontainers 통합 테스트 또는 `jdbc:tc:`·localhost URL), `validate` | Community판은 undo가 없다(확인 필요: 사용 중인 에디션). 되돌리기 대신 "새 마이그레이션은 앞으로만 간다"를 보고 |
| Liquibase | `update` 후 `status`가 비어 있는지 | `update-testing-rollback`(적용→롤백→재적용) |
| EF Core | `dotnet ef database update`(로컬 연결 문자열 명시) | `dotnet ef database update <직전 마이그레이션>` 후 다시 최신으로 |

- `migration.testcontainers`가 true면 먼저 기존 통합 테스트를 `single_test`로 돌린다. Spring Boot·EF 테스트가 시작할 때 마이그레이션을 적용하므로 가장 싼 증거다.
- EF Core: `dotnet ef migrations script --idempotent`로 SQL을 뽑아 리뷰에 붙인다. 모델과 마이그레이션 불일치는 `dotnet ef migrations has-pending-model-changes`(EF 8 이상, 추정: 버전 확인 필요)로 본다.
- Docker가 없으면 3절을 건너뛰고 "마이그레이션 실행 검증 못 함"으로 보고한다. 성공으로 적지 않는다.

## 4. 보고 형식
명령마다 한 줄. 출력에서 숫자를 그대로 옮긴다.

```
- ./gradlew spotlessCheck → 통과 (exit 0)
- ./gradlew test --tests 'com.x.OrderServiceTest' → 12 passed, 0 failed
- ./gradlew test → 실패: 1 failed (InventoryTest.reserve) — 원인 …
- 마이그레이션: 못 함(Docker 없음)
```
돌리지 않은 단계는 "안 함"과 이유를 적는다. 돌리지 않은 명령의 결과를 쓰지 않는다.
