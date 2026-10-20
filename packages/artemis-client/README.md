# Artemis Client — 호환 패키지

기존 `artemis_client` 공개 import 및 DTO 호환성을 위해 보존한 원격 Python SDK임.
Callisto는 HTTP Daemon이나 원격 서버를 제공하지 않으며, 이 패키지를 통해
Android 자연어 테스트를 실행하지 않음. 현재 실행은 [Callisto 빠른 시작](../../README.md)의
`callisto run`과 로컬 Pro 엔진을 사용함.

- 정식 배포 소스: `src/artemis_client/`. Callisto wheel과 독립 `artemis-client` 빌드에서 사용됨.
- 루트 `artemis_client/`: 저장소에서 직접 실행할 때의 기존 import 호환용 복사본임.
  공개 모듈 경로와 소스 실행 환경을 변경하지 않기 위해 이번 정리에서는 유지됨.
- `artemis.interfaces.sdk`와 `artemis`의 지연 공개 export가 이 패키지를 참조함.
- `tests/`는 mock HTTP 계약 회귀이며 Callisto 원격 서버 지원을 의미하지 않음.
- `examples/basic.py`와 [원본 설계](DESIGN.md)는 과거 원격 SDK 참고용임.
  [과거 README](../../docs/archive/upstream-client-readme.md)는 별도 보관됨.

의존성·공개 함수·기존 설치 경로와 패키지 버전은 변경하지 않음.
