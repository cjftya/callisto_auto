# Callisto 전환 진행 상황 — 2026-10-19

## 실행 범위 수정

사용자가 Work 내부 AI CLI 실행을 하지 않고 구현을 진행하도록 명시했어요.
과거 Work 중첩 CLI 실행 실패를 P1~P4 개발의 차단 조건으로 사용하지 않아요.
실제 공급자·Android 검증은 대상 PC에 남기며, 오프라인 테스트로 대체 통과 처리하지 않아요.
반영 대상 브랜치는 사용자가 지정한 `master`이며 저장소 기본 `main` 설정은 변경하지 않아요.

## 구현

| 단계 | 상태 |
|---|---|
| P0 실제 CLI 기능 검증 | 대상 PC에 보류. Work에서 실행 금지 |
| P1 선별 이관·라이선스·기준 SHA | 완료 |
| P2 LangChain CLI 어댑터·native 통신 경계 | 초기 Codex 구현/오프라인 계약 검증 완료. 공급자별 기능 차이 존재 |
| P3 standalone·웹/외부 MCP/Flash 실행 제거 | 완료. Pro 공유 코드 보존 |
| P4 Callisto CLI·Skill·설치 및 사용자 PC 검증 스크립트 | 구현 완료 |
| P5 회귀·패키징 | 아래 오프라인 검증 완료. 실제 계정/기기/Windows 검증 미완료 |

기존 Pro Planner/Operator/Explorer/Validator/Checker/Diagnoser/Summarizer/Outputter와
그래프, 체크포인트, 상태·복구, ADB/Helper, Trace를 유지했어요.
보존 대상의 원본 해시는 `upstream-preserved-manifest.json`과 자동 테스트로 확인해요.

## 검증 증거

환경: Linux x86_64, Python 3.12.14. 실제 AI CLI는 실행하지 않았어요.

- `python -m pytest -q --tb=short`: **2076 passed, 27 skipped, 8 deselected**.
  skip 27개에는 Work PID namespace와 host `/proc` 불일치 때문에 실행하지 않은 원본 생존/잠금 테스트 17개가 포함돼요. 이 17개는 정상 PID 환경의 사용자 PC/CI에서는 실행돼요.
  경고 87개는 주로 원본 Pillow deprecated API 및 mock GenAI thinking-level 값 관련이에요.
- 초기 독립 검증: Pro 그래프/체크포인트/문맥/기존 Universal 경로/구조화 응답 249개 통과.
- Callisto 어댑터/경계 테스트 39개 통과. timeout/cancellation은 fake Python 자식 프로세스로 확인해요.
- 부분 출력·비정상 종료·잘못된 도구 이름/ID/인자/schema 거부, 이미지 순서/메시지 이력,
  structured output, 요청 직렬화, 제한된 출력, 민감 원문 비노출을 확인했어요.
- 실제 SDK 호출을 만들던 경로는 CLI factory/native port 또는 명시적 미지원 오류로 바꿨어요.
- 기존 readiness의 API 키 수집·반환을 제거하고 CLI 경로 존재 검사로 교체했어요. 공식 로그인·추론은 미검증으로 표시해요.
- `python -m pip check`: 깨진 의존성 없음.
- editable 설치 및 frontend 없는 wheel 빌드 성공.
- wheel의 Pro 그래프/내부 액션 세션/기본 설정/라이선스 포함과 웹/외부 MCP/Flash runner 제외 확인.
- 별도 설치 디렉터리에서도 기본 설정 로딩, Pro import, CLI help 성공. 실제 AI CLI 실행 없음.
- 제거된 원본 구성요소 테스트는 `tests/upstream_removed/`에 보관했어요.
  일부 혼합 테스트 파일은 원래 계약의 검사만 보관하고 Pro/공유 검사는 계속 실행해요.

자동 테스트의 `CALLISTO_FORBID_LIVE_CLI=1`은 실제 AI CLI 실행을 차단해요.
모든 stderr 401을 전체 인증 실패로 분류하던 이전 준비 검사 도구는 제거했어요.
새 어댑터는 플러그인 stderr 경고를 성공한 모델 응답의 실패로 덮어쓰지 않아요.

## 남은 실제 검증 및 미지원 기능

- 사용자 PC의 `tools/verify_local_cli.py --allow-live-cli`로 실제 Codex 텍스트/이미지/JSON/tool call/여러 턴 확인.
- 실제 Android 또는 에뮬레이터에서 자연어 테스트, 좌표 정확도, 기기 연결 오류, 복구·체크포인트·Trace 확인.
- 실제 공급자 긴 입력·인증 실패·취소·timeout 및 Windows 프로세스 정리 확인.
- Claude 텍스트 transport는 실험 구현, 이미지 미구현. Gemini CLI 미구현.
- native Files/Interactions/agentic video/cloud cache/audio/server-side search 등 미지원.
  실제 native 기능과 Universal 프레임 경로의 동등성을 보장하지 않아요.
- OCR CLI 포트는 opt-in이며 실제 인식/좌표 정확도 검증 전이에요.

이 상태를 “계획서의 모든 기능 동등성·실기기 검증까지 완료”로 해석하면 안 돼요.
현재 산출물은 API 키 없이 동작하도록 전환한 Pro 런타임과 CLI 어댑터의 첫 구현이에요.

최종 결과 JSON은 task status와 test status를 구분해요. 완료지만 검증 항목이 없으면 `test_status=not_reported`이며 테스트 통과로 표시하지 않아요.
