# 실수 기록

버그를 고칠 때마다 실수의 종류를 한 줄씩 추가한다(`bug-fix` 9단계). 이 파일은 커밋한다 — 다른 PC·팀원·CI가 같은 횟수를 본다.
`python3 <knack>/skills/mistake-proofing/scripts/mistakes.py check .`는 2회 이상 나온 태그에 `docs/enforcement.md`의 증명된 행이 없으면 실패한다.
- 한 행이 한 번의 발생이다. 태그는 실수의 종류(`mistake:missing-tx-boundary`)이지 버그 이름이 아니다. 이미 있는 태그를 먼저 쓴다.
- 버그 기록: PR·이슈·커밋 링크, 또는 `.design/bug-<slug>/BUGFIX.md`(로컬 맥락). 같은 태그·같은 기록의 행은 한 번으로 센다.
- 두 브랜치가 동시에 행을 추가해 병합 충돌이 나면 두 행을 모두 남긴다.
- 칸 안의 `|`는 `\|`로 적는다. 코드·개인정보·운영 데이터는 적지 않는다.

| 날짜 | 태그 | 한 줄 요약 | 버그 기록 |
|---|---|---|---|
| <YYYY-MM-DD> | `mistake:<slug>` | <무엇을 빠뜨렸나> | <PR·이슈·커밋 · .design/bug-<slug>/BUGFIX.md> |

<!-- 출처: pstack principle-encode-lessons-in-structure (MIT, Lauren Tan, cursor/plugins@1ba91fc) · knack THIRD_PARTY_NOTICES.md -->
