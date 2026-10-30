---
name: verify-<앱>
description: <앱>(<Spring Boot|ASP.NET Core> <표면: REST API 등>)를 로컬에서 띄우고 <주요 기능>을 호출해 동작을 증거로 남긴다. 기능 구현·버그 수정의 검증 단계에 사용.
---

# Verify <앱>

상태: **미증명** (EVIDENCE.md의 한 실행에서 띄우기·점검·정리와 기능 하나 이상이 통과하면 "증명됨 · <날짜> · <commit>"으로 바꾼다)
빌드·테스트(`stack-verify`)가 통과한 뒤에 돌린다. 이 스킬은 앱을 띄워 동작을 확인하는 단계다.
기능 목록: [features/README.md](features/README.md) · 실행 기록: [EVIDENCE.md](EVIDENCE.md)

## 띄우기
- 기동 전: 앱·의존 자원 포트가 모두 비었는지(`<lsof -iTCP:8080 -iTCP:5432 -sTCP:LISTEN>`), 고른 프로파일의 datasource·브로커가 localhost/컨테이너인지 확인한다. compose 파일에 고정 `container_name`이 있으면 멈추고 보고한다
- 의존 자원: 실행마다 새 프로젝트 이름(`verify-<앱>-<타임스탬프>`)을 정해 EVIDENCE.md에 먼저 적고, 그 이름을 명령에 그대로 쓴다: `<docker compose -p verify-<앱>-<타임스탬프> -f compose.yaml up -d db>` — 준비 신호: `<pg_isready -h localhost -p 5432>`
  - Spring Boot docker-compose 지원(3.1+)을 쓰는 레포면 `<spring.docker.compose.enabled=false>`로 끄고 위 명령으로 띄운다
- 앱: `<./gradlew bootRun --args='--spring.profiles.active=local' | dotnet run --project src/Api --launch-profile <로컬 프로필> | ASPNETCORE_ENVIRONMENT=Development dotnet run --project src/Api --no-launch-profile>`
  - `bootRun`·`dotnet run`은 앱을 자식 프로세스로 띄운다. 준비 신호 뒤 `<lsof -tiTCP:8080 -sTCP:LISTEN>`으로 리스너 PID를 기록한다(`$!`는 런처 PID)
  - 포트: `<8080>` · 필요한 환경 변수: `<없음 | 이름=로컬 값>` · 시드: `<명령 또는 자동>`
- 준비 완료: `<curl -fsS localhost:8080/actuator/health>`가 `UP`이고, `<시드 확인 명령>`이 기대 값을 낸다
- 운영·공유 자원(운영 프로파일, 원격 DB)은 쓰지 않는다

## 점검 (doctor, 읽기 전용)
조작 전에, 그리고 조작이 실패한 뒤마다 돌린다.
- `<curl -fsS localhost:8080/actuator/health>` → UP
- 포트를 이번에 띄운 프로세스가 쓰는지: `<lsof -tiTCP:8080 -sTCP:LISTEN>`이 기록한 리스너 PID와 같다
- 빌드가 지금 커밋인지: 기동 로그의 버전 (`/actuator/info`는 노출 설정과 git 정보 플러그인이 있을 때만)

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
- 이번에 띄운 PID와 컨테이너만 멈춘다: `<kill <리스너 PID> <런처 PID>>`, `<docker compose -p verify-<앱>-<타임스탬프> -f compose.yaml down -v>`(EVIDENCE.md에 적은 이번 실행 이름 그대로. 셸 변수·빈 이름은 쓰지 않는다 — 비면 기본 프로젝트를 지운다. 전용 프로젝트라 볼륨까지 지워 다음 실행이 빈 상태에서 시작한다). 기동 전에 떠 있던 것과 프로세스 이름으로는 건드리지 않는다
- 증거 폴더는 남긴다. 정리 뒤에 증거가 그 위치에 있는지 확인한다

<!-- 출처: pstack (MIT, Lauren Tan, cursor/plugins@1ba91fc) · knack THIRD_PARTY_NOTICES.md -->
