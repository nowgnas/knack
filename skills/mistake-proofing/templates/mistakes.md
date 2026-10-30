# 실수 기록

버그를 고칠 때마다 실수의 종류를 한 줄씩 추가한다(`bug-fix` 9단계). 이 파일은 커밋한다 — 다른 PC·팀원·CI가 같은 횟수를 본다.
`python3 <knack>/skills/mistake-proofing/scripts/mistakes.py check .`는 2회 이상 나온 태그에 `docs/enforcement.md`의 증명된 행이 없으면 실패한다. 스크립트는 knack 레포에 있으므로 CI에서 돌리려면 CI가 knack 레포도 체크아웃해야 한다.
- 한 행이 한 번의 발생이다. 태그는 실수의 종류(`mistake:missing-tx-boundary`)이지 버그 이름이 아니다. 이미 있는 태그를 먼저 쓴다.
- 버그 기록: PR·이슈·커밋 링크나 이슈 키. 커밋 전이라 아직 없으면 버그마다 겹치지 않는 `bug-<slug>-<날짜>`를 적고, PR이 생기면 링크로 바꾼다. 같은 태그·같은 기록의 행은 한 번으로 센다(PR·이슈 링크는 레포·번호로 비교하고, `#12`·`PR #12`는 원장의 링크가 한 레포뿐일 때 그 레포의 12번과 같다) — cherry-pick·병합으로 같은 행이 두 번 들어와도 한 번이다. `-`(기록 없음)는 행마다 따로 세므로 쓰지 않는다.
- 두 브랜치가 동시에 행을 추가해 병합 충돌이 나면 두 행을 모두 남긴다.
- 칸 안의 `|`는 `\|`로 적는다. 코드·개인정보·운영 데이터는 적지 않는다.

| 날짜 | 태그 | 한 줄 요약 | 버그 기록 |
|---|---|---|---|
| <YYYY-MM-DD> | `mistake:<slug>` | <무엇을 빠뜨렸나> | <PR·이슈·커밋 · bug-<slug>-<날짜>> |

<!-- 출처: pstack principle-encode-lessons-in-structure (MIT, Lauren Tan, cursor/plugins@1ba91fc) · knack THIRD_PARTY_NOTICES.md -->
