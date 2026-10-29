---
name: verify-<앱>
description: <앱>(<Spring Boot|ASP.NET Core> <표면: REST API 등>)를 로컬에서 띄우고 <주요 기능>을 호출해 동작을 증거로 남긴다. 기능 구현·버그 수정의 검증 단계에 사용.
---

# Verify <앱>

상태: **미증명** (EVIDENCE.md에 실제 실행 기록이 생기면 "증명됨 · <날짜> · <commit>"으로 바꾼다)
기능 목록: [features/README.md](features/README.md) · 실행 기록: [EVIDENCE.md](EVIDENCE.md)

## 띄우기
- 의존 자원: `<docker compose -f compose.yaml up -d db>` — 준비 신호: `<pg_isready -h localhost -p 5432>`
- 앱: `<./gradlew bootRun --args='--spring.profiles.active=local' | dotnet run --project src/Api --environment Development>`
  - 포트: `<8080>` · 필요한 환경 변수: `<없음 | 이름=로컬 값>` · 시드: `<명령 또는 자동>`
- 준비 완료: `<curl -fsS localhost:8080/actuator/health>`가 `UP`이고, `<시드 확인 명령>`이 기대 값을 낸다
- 운영·공유 자원(운영 프로파일, 원격 DB)은 쓰지 않는다

## 점검 (doctor, 읽기 전용)
조작 전에, 그리고 조작이 실패한 뒤마다 돌린다.
- `<curl -fsS localhost:8080/actuator/health>` → UP
- 포트를 이번에 띄운 프로세스가 쓰는지: `<lsof -iTCP:8080 -sTCP:LISTEN>`의 PID가 기록한 PID와 같다
- 빌드가 지금 커밋인지: `<curl -fsS localhost:8080/actuator/info>` 또는 기동 로그의 버전

## 조작
- 기능별 절차는 `features/<기능>.md`. 이 레포의 실제 엔드포인트·본문을 쓴다(예시가 아니라)
- 인증: `<로컬 토큰 발급 명령 | 없음>`
- 두 벌을 띄울 수 `<있다(포트·DB 이름 변경) | 없다 — 이미 떠 있는 인스턴스를 남이 쓰고 있으면 조작하지 않는다>`

## 증거
- 위치: `<.verify-evidence/<날짜>-<기능>/>` (gitignore에 추가. 정리 단계에서 지우지 않는다)
- 남길 것: 요청과 응답(상태 코드·본문), 바뀐 DB 행(`<psql | sqlcmd> 로컬 조회`), 관련 로그 줄, 발행된 메시지
- 기준: 실제 사용자 경로(공개 API)로 부른다. 테스트 전용 엔드포인트·내부 setter로 상태를 만들지 않는다. 화면(응답)만이 아니라 부작용(행·메시지·파일)도 확인한다. 목(mock)은 운영에서도 경계 밖인 외부 시스템에만 쓴다
- dry-run·테스트 모드를 쓰면 실제로 무엇을 건너뛰는지 관찰로 확인한다(이름을 믿지 않는다)

## 정리
- 이번에 띄운 PID와 컨테이너만 멈춘다: `<kill <기록한 PID>>`, `<docker compose -f compose.yaml down>`. 프로세스 이름으로 죽이지 않는다
- 증거 폴더는 남긴다. 정리 뒤에 증거가 그 위치에 있는지 확인한다

<!-- 출처: pstack (MIT, Lauren Tan, cursor/plugins@1ba91fc) · knack THIRD_PARTY_NOTICES.md -->
