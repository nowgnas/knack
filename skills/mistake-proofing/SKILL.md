---
name: mistake-proofing
description: 같은 실수가 두 번째로 나면 지시문을 더 쓰지 않고 테스트·린트·스크립트로 강제하고 docs/enforcement.md에 증명과 함께 기록한다. "이 실수 다시 안 나게 해줘"에 사용.
---

# Mistake Proofing

같은 실수를 두 번 하면 문서가 아니라 구조가 막아야 한다. 같은 지시를 두 번째 쓰고 있다면 그 지시가 증상이다.
판정 근거는 레포에 **커밋되는** `docs/mistakes.md`(발생 원장)와 `docs/enforcement.md`뿐이다. `.design/`의 `BUGFIX.md`는 커밋되지 않으므로 맥락용이고 세지 않는다.

## 1. 태그
- `bug-fix` 9단계에서 `docs/mistakes.md`에 한 줄을 추가한다(없으면 사용자 확인 후 `templates/mistakes.md`로 만든다): `| 날짜 | mistake:<slug> | 한 줄 요약 | 버그 기록 |`. slug는 실수의 종류(예: `mistake:missing-tx-boundary`), 버그 이름이 아니다. 버그 기록 칸은 PR·이슈 링크, 아직 없으면 `bug-<slug>-<날짜>`. 수정 커밋에 함께 넣는다.
- `BUGFIX.md`를 쓰는 경우 "재발 방지"에도 같은 태그를 적어 맥락을 잇는다(세는 것은 원장뿐).
- 비슷한 태그가 이미 있으면 새로 만들지 않고 그 태그를 쓴다. 목록: `python3 <이 스킬 폴더>/scripts/mistakes.py list <레포>`

## 2. 재발 판정
- `mistakes.py list <레포>`: 태그별 횟수와 버그 기록. **2회 이상**이면 이 스킬의 대상이다.
- `mistakes.py check <레포>`: 2회 이상인 태그에 `docs/enforcement.md` 표의 증명된 행(또는 "강제 불가 — <실제 이유>")이 없으면 exit 1. 원장이 커밋되므로 어느 PC·clone에서 세어도 같은 횟수다(CI에서 돌리려면 CI가 knack 레포도 체크아웃한다). 원장 형식이 틀리면 exit 2.
- 사용자가 "또 이러네"라고 정정한 것도 같은 신호다. `bug-fix` 밖(리뷰·대화)에서 정정돼도 그 자리에서 원장에 한 줄 추가한다: 기록 칸은 고친 커밋·PR, 아직 없으면 `bug-<slug>-<날짜>`(PR이 생기면 링크로 바꾼다).
- 원장으로 옮겼다는 표시("…추가했다: 예"·"docs/mistakes.md 로 옮김")가 없는 `BUGFIX.md`에 태그가 있으면 `list`·`check`가 "참고:" 줄로 알린다(종료 코드는 그대로). 원장에 행으로 옮기고 그 파일에 "docs/mistakes.md 로 옮김"을 적는다.

## 3. 강제 수단 고르기 (위가 강하다)
| 수단 | Spring Boot | .NET |
|---|---|---|
| 타입·컴파일 | 값 객체, sealed 계층, `@NullMarked`·`@Nullable`(JSpecify) + ErrorProne/NullAway | nullable 참조형 + `TreatWarningsAsErrors`, 값 객체 |
| 아키텍처 테스트 | ArchUnit | NetArchTest·ArchUnitNET |
| 린트·분석기 | Checkstyle·PMD·ErrorProne 규칙 | Roslyn 분석기, `.editorconfig` 심각도 `error`(IDE 규칙은 `EnforceCodeStyleInBuild`) |
| 테스트 | 실패 사례를 고정한 단위·통합 테스트 | 같음 |
| 스크립트·CI·훅 | 빌드 단계, pre-commit, knack 훅 | 같음 |
- 판단이 필요해 구조로 못 막으면 지시문을 눈에 띄는 자리(해당 스킬·룰의 맨 위)로 옮기고 실패 예시를 붙인다. 이 경우 표에 "강제 불가 — <실제 이유>"로 적는다(`사유`·`<...>`를 그대로 두면 `check`가 미완성으로 본다).

## 4. 과거 실패로 증명한다
- 강제 수단을 실패가 있던 코드(도입 커밋, 재현 테스트의 수정 전 상태)에 적용해 **실패하는 것**을 확인하고, 수정 후 코드에서는 통과하는 것을 확인한다.
- 과거 커밋은 작업 트리를 바꾸지 않게 따로 꺼낸다: `git worktree add --detach ../proof-<slug> <sha>` → 그 폴더에 강제 수단을 복사해 실행 → `git worktree remove ../proof-<slug>`. `checkout`·`stash`로 현재 작업을 옮기지 않는다.
- 증명은 실행 명령, exit 코드, 출력 한 줄로 남긴다. 증명하지 못한 강제 수단은 "미증명"으로 적는다(`check`는 미증명·빈 칸 행을 강제로 보지 않는다).

## 5. 기록과 정리
1. `templates/enforcement.md` 형식으로 `docs/enforcement.md`에 행을 추가한다(없으면 만든다): 태그 · 룰 · 강제 수단 · 실행 명령 · 과거 실패 증명.
2. 구조로 막았으면 같은 내용의 지시문은 지우거나 표 링크로 줄인다(사용자 확인 후). 지시와 구조를 둘 다 두지 않는다.
3. 다시 `mistakes.py check <레포>`가 exit 0인지 본다.
4. 보고: 태그, 횟수, 고른 수단과 이유, 증명 결과, 지운 지시문. 커밋·PR은 사용자 확인 후.

<!-- 출처: pstack principle-encode-lessons-in-structure (MIT, Lauren Tan, cursor/plugins@1ba91fc) · THIRD_PARTY_NOTICES.md -->
