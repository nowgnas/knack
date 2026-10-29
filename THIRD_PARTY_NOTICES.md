# Third-party notices

knack는 아래 오픈소스 프로젝트의 아이디어를 한국어로 다시 써서 일부 스킬에 반영했습니다. 원문을 그대로 복사하지 않았지만, 출처와 라이선스를 밝힙니다.

## pstack

- 저장소: https://github.com/cursor/plugins (`pstack/`)
- 기준 리비전: `1ba91fc25c0977741dd0e267849e6234b037ed0a`
- 저작자: Lauren Tan
- 라이선스: MIT (`pstack/LICENSE`, 전문은 아래)

| 원문 경로 (pstack) | 반영한 knack 파일 | 반영한 아이디어 |
|---|---|---|
| `pstack/skills/blast-radius/SKILL.md` | `skills/impl-review/references/review-checklist.md`, `skills/impl-review/SKILL.md`, `skills/impl-review/templates/REVIEW.md`, `agents/impl-reviewer.md` | 증명 단계(1~5), 변경이 안전한 핵심 사실 하나를 찾아 증명, grep이 닿지 않는 영향 범위, 확인하고 제외한 위험 |
| `pstack/skills/principle-prove-it-works/SKILL.md` | `skills/impl-review/SKILL.md` | 대리 지표가 아니라 실제 실행으로 확인, 다시 돌릴 수 있는 증명 기록 |

```
MIT License

Copyright (c) 2026 Lauren Tan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
