# <기능명> 완료 게이트

> 설계: [PLAN.md](PLAN.md) · 상태: `knack gate status <이 파일>` · 보고 직전: `knack gate reverify <이 파일>`
> 규칙: `knack show ref high-risk-gates` — 게이트 하나에 관찰 가능한 결과 하나, 통과는 exit 0 과 기대 출력 일치

- [ ] G1: <결과 — 예: 같은 멱등키로 동시에 10건 요청하면 결제 승인은 1건이다>
  CHECK: ./gradlew test --tests '*PaymentIdempotencyIT*'
  EXPECT: BUILD SUCCESSFUL
  EVIDENCE: pending

- [ ] G2: <결과 — 예: 마이그레이션 down 후 스키마 덤프가 적용 전과 같다>
  CHECK: <명령>
  EXPECT: <성공할 때만 나오는 출력 또는 /정규식/>
  EVIDENCE: pending

- [ ] G3: <명령으로 판정할 수 없는 결과 — 예: 배포 순서(Expand → 배포 → Contract)를 팀과 합의했다>
  EVIDENCE: pending
