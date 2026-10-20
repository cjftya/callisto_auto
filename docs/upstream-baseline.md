# ARTEMIS 원본 기준선과 보존 경계

원본: https://github.com/google/artemis

기준 SHA: `351ca8422f7b5b54e80a9c1ce03a222e02415b6b`.
별도 원본 checkout의 HEAD와 817개 추적 파일을 확인했어요. 대상 Git 이력에는 원본 `.git`을 합치지 않았어요.

## 이관

- `artemis/`의 Pro 그래프, 에이전트, 데이터 엔진, 로컬 SDK, ADB/Helper, 내부 액션 세션, 도구·리소스.
- `third_party/mobile_use/` 및 Apache-2.0 LICENSE, NOTICE, METADATA.
- Accessibility Helper 소스와 원본 테스트/fixture. 사용자 인증정보, 캡처, 로그, 빌드 산출물은 이관하지 않아요.
- 원본 호환 DTO/client 패키지는 Python SDK import를 유지하기 위해 포함해요. Callisto 실행 경로가 원격 HTTP 서버를 요구하지는 않아요.

`docs/upstream-preserved-manifest.json`에는 Pro 그래프·핵심 에이전트·프롬프트의 원본 SHA-256이 있어요.
자동 테스트가 실제 이관 파일의 동일성을 확인해요. Explorer·영상 분석의 변경은 모델 통신 및 키 의존 엔진 선택 경계예요. 기존 Universal 알고리즘을 사용해요.

## 변경 지점

- `artemis/llm/router.py`: 직접 공급자 SDK 생성 제거, CLI provider만 허용.
- `artemis/services/llm.py`: 기존 gateway·재시도·fallback·trace는 유지. 공유 요약기의 legacy Google factory도 CLI로 연결.
- `artemis/sdk/agent.py`: API 사전 ping/GenAI/Google LangChain client 생성 제거. 실제 CLI 사전 실행도 하지 않음.
- `artemis/agents/explorer/explorer.py`, `video_analyzer/video_analyzer.py`: Google SDK Client 대신 CLI native inference port.
- `third_party/mobile_use/sdk/agent.py`: FlashRunner import와 실행 분기 제거, Pro 요청만 허용. Pro else suite의 처리 흐름은 유지.
- `artemis/interfaces/cli/commands/run.py`: Daemon dispatch 제거, standalone 실행 유지.
- `artemis/runtime/`: web daemon client/lifecycle 제거. 로컬 device pool, locks, awake, cancellation, supervisor 유지.
- `artemis/utils/ocr_api.py`: 선택적 OCR 모델 통신을 CLI 포트로 교체; 출력 text/position 계약 유지.
- `artemis/data_engine/engine.py`: lazy CLI import에서 드러난 순환 참조를 피하도록 CURRENT_TRACE_ID를 원래 정의 모듈에서 직접 import. 추가로 2026-10-21 시작 전 `join()` 경쟁과 후속 저장 누락을 막기 위해 스레드 등록·시작·정리를 같은 락으로 동기화하고 저장 대기를 통일함. 이 파일은 두 보존 manifest에 포함되지 않으며 해시는 변경하지 않음. 저장 포맷·Trace·async task 경로·Pro 그래프는 유지함. 제한적 변경 근거와 회귀는 [후속 수정 기록](maintenance/data-engine-followup.md) 참조.
- `artemis/core/diagnostics/probes/credentials_probe.py`: 키 원문 수집·노출을 없애고 CLI 설치 여부만 확인. 로그인/추론 검증으로 표시하지 않음.
- 설정 provider 검증: API key 대신 CLI provider 검증. 기본 CLI 모델로 통일하며 공급자 전용 정확도 동등성은 미확인.
- `pyproject.toml`: frontend/Cython 빌드 전제·웹/직접 모델 SDK 의존성 제거. Google SDK types는 native 데이터 계약에 필요해 유지.

## 제외 및 보관

`apps/showcase_ui/`, `apps/admin_console/`, `mcp_server/`와 웹 CLI 명령은 이관하지 않았어요.
Flash 실행 runner는 제거했으나 Pro가 사용하는 Flash 폴더의 summarizer/context_compressor와 Explorer flash tier는 보존했어요.
제거한 구성요소의 테스트는 `tests/upstream_removed/`에 보관해요. 목록·사유는 `docs/archived-tests.json`에 있어요.
API factory/웹 빌드 테스트는 Callisto의 no-API 경계와 wheel 설치 테스트로 대체해요.

원본 native 테스트가 실제 API 키 없이도 mock native 경로를 선택하도록 명시적 fake native client/엔진 fixture를 사용해요. API 키로 엔진을 선택하지 않아요.
Pro queue/SDK 테스트의 실행 프로필은 Flash에서 Pro로 갱신했어요. 모델 기본값 및 CLI 명령 집합을 검사하는 테스트도 새 계약에 맞췄어요.

Work에서는 `/proc/self`가 노출하는 host PID와 `os.getpid()`가 다른 경우가 확인됐어요. 실제 PID 생존에 의존하는 원본 테스트 17개에만 환경 조건 skip을 적용하고, 운영 기기 잠금 코드는 유지했어요. 이 조건이 없는 CI/실제 PC에서는 해당 테스트가 그대로 실행돼요.

## v4.1 추가 보존 검사

원본 Explorer·영상 엔진·액션 server/session 23개 Python 파일을 `upstream-engine-manifest.json`으로 추가 고정했어요. 기존 32개 해시는 바꾸지 않아요. `CALLISTO_EXPLORER_ENGINE=native`로 원본 Native 루프를 CLI 호환 포트에 연결할 수 있고 기본 Universal 경로는 유지해요. 자세한 미지원 및 실사용 검증 구분은 [지원 범위](cli-capability-matrix.md)를 참고하세요.
