# <기능 이름>

<사용자 관점 한두 줄: 무엇을 하는 기능인지>

## 세부 기능
- <예: 주문 생성 · 재고 부족 시 거절 · 같은 요청 재전송 시 중복 생성 안 함>

## 사용자는 어떻게 닿는가
- <예: 앱의 "주문하기" → `POST /api/orders`>
- 전제: <인증 · 시드 데이터 · 외부 시스템>

## 조작 방법
```bash
<curl -sS -X POST localhost:8080/api/orders -H 'Content-Type: application/json' -d '{"productId":1,"qty":2}'>
```
- 통과 기준: <상태 코드 201, 본문의 id, `orders` 테이블에 행 1개, `OrderCreated` 메시지 1건>

## 주의
- <시드에 전제가 없으면 실패로 보고하고 이유를 여기에 적는다. 통과시키려고 절차를 약하게 바꾸지 않는다>

<!-- 출처: pstack (MIT, Lauren Tan, cursor/plugins@1ba91fc) · knack THIRD_PARTY_NOTICES.md -->
