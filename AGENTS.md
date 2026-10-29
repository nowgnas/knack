# knack 레포 작업 가이드

개인용 에이전트 하네스. 스킬·룰·훅·서브에이전트의 원본을 이 레포에 두고, `install.sh`가 각 에이전트 설정에 연결한다.

## 구조
- `rules/*.md` — 룰. frontmatter `load: always`(매 세션 주입)는 짧게, 가끔 필요한 것은 `load: on-demand` + `when:`
- `skills/<name>/SKILL.md` — 에이전트 중립 스킬. 스크립트는 `skills/<name>/scripts/`
- `agents/*.md` — 서브에이전트. `task:`(models.json 작업 유형)로 모델이 정해지고, Claude 파일·Codex 역할로 생성된다. `sandbox:`는 Codex 역할에만 적용
- `models.json` — 작업 유형 → 티어 → 에이전트별 모델·effort, `main`은 세션 기본 모델. 변경은 `knack model set`.
  모델은 이름 하나 또는 후보 목록(`["gpt-6-astra", "gpt-6-sol"]`)으로 적고, 설치된 첫 모델이 쓰인다. PC 전용 값은 `~/.config/knack/models.local.json`에 두면 덮어쓴다(커밋되지 않음)
- `hooks/<name>/hook.json` + 스크립트 — 훅. `targets`에 에이전트별 event/matcher
- `lib/knack.py` — list/show/search/doctor/add/new/adopt/hook/model, 외부 항목 조회(Claude Code·데스크톱 앱 플러그인 포함), 훅·모델 설정 동기화
- `lib/gate.py`, `lib/persona.py` — 완료 게이트 확인·재검증, 페르소나 (`knack gate`, `knack persona`)
- `persona/` — 페르소나 템플릿. 실제 `core.md`·`detail/`은 개인 정보라 gitignore
- `bin/knack` — CLI (글로벌 설치 시 `~/.local/bin/knack`)
- `install.sh` — 설치/상태/제거. `tests/smoke.sh` — 스모크 테스트

## 사용자가 "적용/설치/업데이트/제거해줘"라고 하면
1. `./install.sh --dry-run [옵션]`으로 변경 예정 사항을 먼저 보여준다.
2. 사용자 승인 후 `--dry-run` 없이 실행한다.
3. `knack doctor`로 결과를 확인해 보고한다.

## 규칙
- 셸 스크립트는 macOS 기본 bash 3.2에서 동작해야 한다 (연관 배열, `mapfile`, `${v,,}` 금지). JSON 처리와 조회 로직은 `lib/knack.py`(python3 표준 라이브러리만)에 둔다.
- 새 스킬을 추가하거나 스킬 절차·CLI 명령·결과물을 바꾸면 `skills/knack-help/USAGE.md`와 `README.md`를 함께 갱신한다.
- 훅 스크립트는 판단할 수 없는 입력을 통과시킨다(fail-open). 에이전트 작업을 훅 오류로 멈추지 않는다.
- 언어: 사람이 읽고 고치는 문서(룰, 스킬 본문, USAGE, 템플릿)는 한국어로 쓴다. 모델만 읽는 문서(서브에이전트 본문, 리뷰 체크리스트)는 영어로 쓰고 출력은 한국어로 하라고 지시한다.
- 스킬 description은 160자 이하로 의도가 드러나게, 본문은 70줄 이하의 목차로 쓰고 세부는 `references/`에 둔다. `knack doctor`가 점검한다.
- 변경 후 `tests/smoke.sh`를 실행한다. push·PR 때 GitHub Actions가 macOS(`/bin/bash` 3.2)와 Ubuntu에서 다시 실행한다.
