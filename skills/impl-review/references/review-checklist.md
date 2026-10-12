# Implementation review checklist

## Principles
- Report only what you verified in code. Every finding needs `path:line` and evidence. Put unverified suspicions under ❔ questions.
- Don't stop at the diff. Read callers of changed code, the reference feature, and related tests.
- Flag convention issues only when they differ from the repo's conventions or the reference feature, not from personal taste.
- No praise and no restating the change. For an item with no issues, write one line: "이상 없음".
- Run the build and related tests when you can (skip if a read-only environment blocks it).
- Write all findings in Korean, using the output format below.

## Severity
| Level | Criteria |
|---|---|
| 🔴 Blocker | Bug, data corruption or loss, security hole, unmet success criterion, broken backward compatibility |
| 🟠 Major | Must fix before merge: missing tests on the core path, possible transaction or concurrency defect, large deviation from conventions, change outside the design scope, a completion gate that passes regardless of behavior |
| 🟡 Minor | Readability, naming, small convention differences |
| ⚪ Nit | Close to taste |
| ❔ Question | A suspicion that needs confirmation |

## What to check
1. **Design fit**: Is every success criterion met by code and tests? Are the policy decisions (DESIGN sections 2, 3, 9) reflected? Any change outside the design?
   - Don't take the implementer's summary or commit messages as evidence. Compare each criterion against the code line by line; missing pieces and unrequested additions are both findings.
2. **Correctness**: boundaries, null, empty collections, state-transition guards, exception paths, dates, time zones, money rounding
3. **Transactions and concurrency**
   - Where the transaction boundary sits, self-invocation, readOnly
   - External API calls inside a transaction
   - Concurrent and duplicate requests (idempotency), locking and versioning
   - Events published only after commit
4. **Data**
   - Migration safety (section 6 of `knack show ref db-migration`)
   - Entity/schema match, indexes, N+1, paging for large reads
5. **Security**
   - Missing authorization (access to other users' resources), input validation, SQL or command injection
   - Personal data or secrets in logs, internal details in error responses
6. **Integrations**: timeouts, idempotent retries, compensation or response on failure, message schema compatibility
7. **Conventions**
   - Compare with the reference feature: package location, naming, layer responsibilities, exception and response style, DI, test style
   - New libraries or patterns introduced
8. **Readability**
   - Names, function size, nesting depth, unnecessary abstraction
   - Comments that restate code, commented-out code, change history in comments
   - Debug code, unused code
9. **Tests**
   - Are success criteria, core branches, and failure paths covered?
   - Would each new test fail without the change? A test that passes on the old code, only asserts that a mock was called, or needs test-only methods added to production code is not coverage.
   - Do test names describe scenarios?
   - Flaky elements (current time, ordering, sleep)
10. **Operations**
    - Log levels and content, metrics
    - New config keys present in every environment's config file, feature flags
11. **Completion gates** (only when a GATES.md is given)
    - Every success criterion is covered by at least one gate
    - No gate passes regardless of behavior: fixed output (`echo ok`), an EXPECT that also appears in failure output, a negative check with no positive control, a number copied from the request as its own proof
    - Manual gates only where no command can decide the outcome; ABANDON entries surfaced, not silently dropped

## Output format (Korean labels)
````
## 리뷰 결과 — 🔴 n · 🟠 n · 🟡 n · ⚪ n · ❔ n
검증 실행: <실행한 명령과 결과 / 실행 못 함(이유)>

### 🔴 Blocker
1. [정확성] <한 줄 요약> — `path:line`
   - 근거: <무엇이 왜 문제인지> · 실패 재현: <입력·상황 → 잘못된 결과나 예외. 보여줄 수 없으면 그렇다고 쓴다>
   - 제안: <수정 방향>

### 🟠 Major
...

### 🟡 Minor / ⚪ Nit
...

### ❔ 질문
...

### 항목별 확인
| 항목 | 결과 |
|---|---|
| 설계 부합 | 이상 없음 / #n |
| 정확성 | |
| 트랜잭션·동시성 | |
| 데이터 | |
| 보안 | |
| 연동 | |
| 컨벤션 | |
| 가독성 | |
| 테스트 | |
| 운영 | |
| 완료 게이트 | 해당 없음 / 이상 없음 / #n |
````
