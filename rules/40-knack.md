---
name: knack
description: 하네스 관리 규칙 — 에이전트 설정은 하네스로 관리하고, 조회는 knack CLI로 필요한 부분만
load: always
---
# 하네스 관리
- 하네스가 관리하는 스킬·룰·훅·서브에이전트는 하네스 레포에서 수정하고 `knack install`로 적용한다. 생성된 설정을 직접 수정하면 이후 설치에서 덮어쓸 수 있다. 절차는 `knack-manage` 스킬을 따른다.
- 설치·추가 전에 `knack list --all`로 하네스와 외부에 이미 있는 항목(같은 이름, 비슷한 기능)을 확인한다.
- 하네스 문서는 통째로 읽지 말고 필요한 부분만 조회한다: `knack list [skills|rules|hooks|agents]` → `knack show <종류> <이름> --toc` → `--section <번호|제목>`. 키워드는 `knack search <키워드>`.
