# 실수 방지 강제 목록

같은 실수가 두 번 난 것만 적는다. 행마다 강제 수단이 과거 실패를 실제로 잡는지 증명한다.
`python3 <knack>/skills/mistake-proofing/scripts/mistakes.py check .`는 2회 이상 난 `mistake:<slug>` 태그가 이 표에 없으면 실패한다.

| 태그 | 룰 | 강제 수단 | 실행 명령 | 과거 실패 증명 |
|---|---|---|---|---|
| `mistake:<slug>` | <한 문장 룰> | <ArchUnit 테스트 `path` · Roslyn 분석기 규칙 · CI 단계 · 강제 불가 — 사유> | `<./gradlew test --tests '*ArchTest' · dotnet build -warnaserror>` | <도입 커밋 `sha`에서 exit 1 "<출력 한 줄>", 수정 후 exit 0 · 미증명> |

<!-- 출처: pstack principle-encode-lessons-in-structure (MIT, Lauren Tan, cursor/plugins@1ba91fc) · knack THIRD_PARTY_NOTICES.md -->
