---
name: repo-onboarding
description: 처음 보는 백엔드 레포 전체를 파악해 온보딩 문서(.onboarding/)를 만든다. "이 레포 파악해줘", "quick으로 온보딩", "onboard this repo" 같은 요청에 사용.
---

# Repo Onboarding

처음 보는 백엔드 레포(Java/Spring, .NET 중심)를 단계적으로 파악해 대상 레포의 `.onboarding/`에 남긴다.
단계별 세부 절차는 필요한 단계만 읽는다: `knack show ref onboarding-phases --section <단계 번호>`.
CLI가 없으면 `references/onboarding-phases.md`, `references/backend-lenses.md`, `references/stacks/`의 해당 파일을 읽는다.

## 모드
| 모드 | 단계 | 용도 |
|---|---|---|
| `quick` | 0–2 | 무엇을 하는 레포인지 빠르게 파악 |
| `standard` (기본) | 0–6 | 개발 투입 전 전반 파악, 핵심 흐름 1개 |
| `deep` | 0–7 | 인수인계 수준, 핵심 흐름 2–3개와 리스크 |

사용자가 관심 영역을 말하면 그 영역에 가중치를 둔다.

## 준비
```bash
mkdir -p .onboarding/flows && printf '*\n' > .onboarding/.gitignore
```
재실행이면 `ONBOARDING.md`의 기준 커밋 이후 변경분(`git log --oneline <sha>..HEAD`)만 반영한다.

## 단계
| # | 목표 |
|---|---|
| 0 | 스택·구조·진입점 단서: `bash scripts/repo-scan.sh <루트> > .onboarding/scan.md` (LLM 추론 없음) |
| 1 | 큰 그림: 역할, 모듈 지도, 런타임 구성, 아키텍처 스타일 |
| 2 | 진입점: HTTP, 메시지 컨슈머, 배치·스케줄러, 러너 |
| 3 | 핵심 흐름: `trace-flow` 절차로 추적 |
| 4 | 데이터: 엔티티·관계, 접근 방식, 마이그레이션, 트랜잭션 경계 |
| 5 | 연동: 외부 API, 메시징, 캐시, 인증·인가 |
| 6 | 운영: 로컬 실행, 테스트, 설정, 배포, 관측성 |
| 7 | 리스크와 열린 질문 (deep) |

- 스택 참조는 스캔으로 판별한 것만, 목차부터 본다: `knack show ref java-spring --toc`, `knack show ref dotnet --toc`, `knack show ref backend-lenses --toc`.
- 서브에이전트를 쓸 수 있으면 1·2·4·5단계를 `repo-explorer`에 관점별로 병렬 위임한다.

## 산출물과 완료 기준
`templates/ONBOARDING.md`, `templates/GLOSSARY.md`, `templates/QUESTIONS.md`를 채워 `.onboarding/`에 저장한다(흐름은 `flows/`).

완료 = 모드의 모든 단계가 문서에 반영되고, 사실 주장마다 `path:line` 근거(미확인은 `(추정)`)가 있으며, 3줄 요약·먼저 읽을 파일 5개·열린 질문 상위 3개를 보고한 상태.
단계 사이에 중간 확인을 받지 않는다. 시크릿 값은 문서에 옮기지 않는다.
