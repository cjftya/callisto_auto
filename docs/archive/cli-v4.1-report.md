> **과거 기록 — 현재 구현 지침이 아님.** 작성 당시의 모델·설치·지원 상태이며, 현재 기준은 [아키텍처](../architecture.md), [지원 범위](../cli-capability-matrix.md), [전환 현황](../migration-status.md)임.

# Callisto v4.1 — 기능 보존·호환성·개선 결과

기준: `main`/`master` = `458fd123`, 원본 ARTEMIS = `351ca8422f7b5b54e80a9c1ce03a222e02415b6b`.
패키지 버전은 `0.1.1`이에요. v4.1은 작업 계획의 버전이에요.

Work에서 실제 Codex/Claude/Gemini 실행·로그인·버전 조회·Android 추론은 수행하지 않아요.
오프라인/CI 성공과 실제 모델·기기 수용 검증은 구분해요.

## 기능 보존·호환성 비교

| 원본 기능 | v4.1 연결·보존 방식 | 판정·남은 차이 |
|---|---|---|
| Pro 그래프·Planner/Operator/Checker/Validator/Diagnoser·Trace·체크포인트·복구 | 기존 32개 보존 manifest의 원본 해시 유지. gateway의 모델 통신만 CLI로 연결 | 오프라인 회귀 대상. 실제 작업 정확도·기기 복구는 미검증 |
| Native Explorer | `CALLISTO_EXPLORER_ENGINE=native`로 원본 native 루프를 CLI native 호환 포트에 연결. 스크린샷·함수 선언/응답·submit 검증 유지 | 선택적 실험 경로. 원본 루프→CLI JSON→submit 왕복은 fake 응답 검증. 실제 모델 미검증 |
| Universal Explorer | 원본 Universal 루프, 화면 인덱스·UI tree prepass·좌표 감사·tier 도구 제한·검증 유지. 기본 경로 | 단순한 새 루프로 재작성하지 않음. Native와 의미·성능 동등성은 미검증 |
| Native Files | upload/get/list/delete 서버 자원 계약은 명시적 UnsupportedCapability | CLI의 로컬 이미지 첨부로 cloud File URI·서버 상태를 재현할 수 없음. 가짜 URI 없음 |
| Interactions·agentic video | 원본 chunk_agentic 및 coordinator 등 소스 보존 | 서버 세션/이벤트/영상 계약에 대응하는 현재 CLI 전송이 없어 미지원. 모델 loop로 임의 교체하지 않음 |
| 정적 영상 분석 | 원본 Universal 키프레임/밀집 액션 프레임·시간표시·blackboard·claim/retry·시각 fallback 보존 | 이미지 경로 구현. 원본 native 영상의 연속 움직임/정확도와 동등하다고 주장하지 않음 |
| 음성 분석 | 원본 추출·분할·native/universal 처리 소스 보존 | 현재 CLI 어댑터의 음성/영상 blob 입력은 명시적 미지원. 영상의 기존 visual fallback은 음성을 검증한 결과가 아님 |
| Context Cache | 원본 context/history/graph checkpoint 유지. CLI에는 전체 이력 전달 | cloud cache 생성·재사용·토큰 과금 계약은 미지원. CLI 내부 캐시 usage와 구별. Native의 명시적 cloud cache 요청은 오류 |
| Server-side Search·grounding | 요청 시 명시적 미지원. 기본 grounding 및 CLI 자체 검색은 비활성화 | CLI의 임의 웹 탐색으로 원래 도구 계약을 대체하지 않음 |
| 이미지 인식 | 원본 이미지·도구 이미지 흐름을 임시 이미지 파일과 CLI `--image`에 연결 | Codex fake 계약 검증. 실제 정확도와 이미지 제한 미검증 |
| OCR | opt-in CLI 이미지→원래 text/polygon 계약. UI tree fallback 유지 | 직접 Vision API 없음. 좌표/인식 정확도·지연은 미검증 |
| Object Detector | 원본 detector.py/JSON·재시도·병렬 제한·좌표 계약 보존 | CLI 모델 경유. Robotics ER 등 원본 특정 모델의 정밀도 동등성 미검증 |
| Accessibility Helper/ADB/UIAutomator2 | 기존 lifecycle·버전/프로토콜·fallback 유지. bundle 경로와 해시 검사 개선 | fake 설치·연결/fallback 회귀. 실제 기기 연결·OEM 동작 미검증 |

추가로 원본 Explorer/영상 엔진 및 action server/session **23개 파일**을 원본 checkout과 바이트 단위로 비교했고 `upstream-engine-manifest.json`에 고정했어요. 기존 32개 해시는 변경하지 않았어요. 새 회귀가 두 manifest를 각각 검사해요. facade의 엔진 선택·전송 경계만 변경하고 native/universal 실행 알고리즘은 보존했어요.

## 수정한 동작

### 인증 환경변수

- `callisto/llm_adapter/environment.py`에서 공통 API Key와 Codex/Claude별 API 엔드포인트·대체 cloud 라우팅 정책을 분리해요.
- 자식 AI 프로세스에만 정책을 적용해요. Windows의 대소문자 혼합 키도 차단해요. 부모 환경은 그대로예요.
- HOME/USERPROFILE/CODEX_HOME/CLAUDE_CONFIG_DIR, OS keychain 발견 및 공식 CLI OAuth 환경은 정상 상속해요. 인증 파일/토큰을 직접 수집·변환·저장하지 않아요.
- CLI 자체에 저장된 인증 종류는 검사하지 않아요. 공식 CLI 로그인은 사용자 PC가 관리해요. 관리자가 강제한 정책을 우회하지 않아요.
- 실제 Python 자식 프로세스가 API 변수를 받지 않고 로그인 경로를 유지하는지 fake 환경으로 검증해요.

### 종료 코드

`callisto/verdict.py`에서 출력 JSON, 저장 JSON, 프로세스 종료 코드를 한 번에 정산해요.

| 조건 | 종료 코드 |
|---|---:|
| 작업 완료 + 유효한 passed 검증 + 실패/미확정/미검증 항목 없음 | 0 |
| 작업 실패 또는 검증 실패 | 1 |
| 완료했지만 검증 없음/잘못된 요약/미확정/unchecked | 2 |
| 취소 | 130 |

`test_status=not_reported`를 0으로 처리하던 문제를 수정했어요. bool/음수/문자열 검증 카운터도 성공으로 해석하지 않아요. 취소/실행 실패는 기존 검증 통계와 별도의 작업 상태로 기록하고 해당 종료 코드를 우선해요.

### CLI 호환성

- Codex의 필수 JSON/schema/이미지/ephemeral/read-only 옵션은 유지해요. 실제 CLI 버전을 실행해 조회하지 않아요.
- unknown option/feature 등 호환성 오류는 원문 stderr를 노출하지 않고 업데이트 안내로 반환해요. 안전 옵션을 제거하는 fallback은 없어요.
- Windows `.cmd`/`.bat` launcher는 shell interpolation 없이 안전하게 실행할 계약을 확보하지 못했으므로 명시적으로 거부해요. 공식 native `.exe`를 설정해야 해요. `doctor`도 launcher 제한을 표시해요.
- 텍스트·이미지·schema·tool ID/인자/응답·전체 이력·timeout/취소 fake 회귀 유지. 실제 버전별 최소 호환 버전은 아직 인증하지 않았어요.
- Claude 텍스트는 계속 실험 단계, 이미지는 미지원이에요. Gemini 구현은 별도 후속 작업이에요.

### 내부 MCP 평가

**이번 버전에서는 제거하지 않아요.** `mcp>=1.26,<2`를 유지해요. 외부 서버를 실행하지 않는 in-process 액션 세션은 요구사항에 부합해요.

`action_session.py`는 단일 owner task와 큐로 액션을 직렬화하며, 호출자 취소가 진행 중인 액션/메모리 스트림을 깨뜨리지 않도록 분리해요. 액추에이터 timeout은 tool 내부에서 발생하고 세션이 죽으면 재생성해요. `action_server.py`는 manifest 기반 schema, typed structuredContent, device 실패와 protocol 실패 구분 및 이미지 응답을 제공해요.

순수 로컬 dispatcher로 대체하는 것은 가능하지만 FastMCP 등록/검증, 결과 types, queue·취소·재생성의 동등한 구현이 필요해요. 단순히 import와 패키지만 지우면 기존 계약이 손상돼요. 원본 액션 구현의 해시와 기존 session·action contract 회귀를 보존하고, Windows CI 범위에도 포함했어요. 제거는 이 동등성 구현과 별도 회귀를 갖춘 후속 변경으로 남겨요.

### 의존성 검토

이번 변경에서는 기능 보존에 필요한 패키지를 추가로 제거하지 않았어요. `mcp<2`는 기존 액션 계약, `google-genai`는 native DTO/types, `langgraph`/`langchain-core`는 Pro 그래프/메시지 계약에 필요해요. `httpx`는 기존 로컬 연결/이미지 처리, OpenCV/ffmpeg/NumPy/SciPy/Matplotlib는 원본 미디어·인지 처리, Jupyter client/ipykernel은 원본 Python 실행 도구를 위해 유지해요. 직접 AI SDK Client 생성·외부 서버 시작 경로의 부재는 정적 경계 회귀로 검사하고, 패키지 설치 가능성은 `pip check`와 clean wheel 설치로 별도 검증해요.

### 스킬과 Helper 배포

- `callisto skill install/update/status`: 정식 Skill을 wheel에서 찾아 사용자 `~/.agents/skills/callisto`로 설치해요. 프로젝트 밖·별도 venv 설치를 검사해요. 패키지 버전과 내용 해시를 기록하고 수정된 파일을 보호해요.
- pip 설치가 사용자 홈을 변경하는 hook은 추가하지 않았어요. 설치 명령이 명시적 한 단계예요. 실제 Codex 스킬 인식은 Work에서 실행하지 않아 미검증이에요.
- `tools/build_helper.py`: 기존 Java 소스와 debug signing identity를 사용해 JDK/Android SDK만으로 Linux/Windows 빌드해요. SDK의 .bat wrapper 대신 Java jar를 직접 호출해요.
- CI는 APK signature 검증, checksum manifest 생성, APK 포함 wheel 빌드·clean 설치를 수행하고 Actions artifact로 제공해요. 기존 debug key의 개발용 배포이며 production 서명·공개 release는 아니에요.
- 기본 source/wheel에는 APK가 없어요. APK를 빌드한 경우에만 wheel에 포함해요. 실행 시 source→wheel의 share 경로를 지원하며 `CALLISTO_HELPER_DIR`가 최우선이에요.
- `callisto helper bundle-status`: device 접근 없이 경로/버전/해시 검사. package/version/checksum이 틀린 번들은 거부해요. 기존 Helper 버전/프로토콜 검사와 UIAutomator2 auto fallback은 유지해요.

## 변경 파일

- 인증/호환: `callisto/llm_adapter/{environment,process,providers,model,native}.py`
- 결과/설치: `callisto/{cli,verdict,skill_install}.py`
- 원본 연결 경계: `artemis/agents/explorer/explorer.py`
- Helper: `artemis/runtime/helper_manager.py`, `artemis/interfaces/cli/commands/helper.py`, `tools/build_helper.py`
- 배포/검증: `pyproject.toml`, `.gitignore`, `.github/workflows/offline.yml`, `tools/verify_wheel.py`
- 회귀/근거: `tests/callisto/test_v41_contracts.py`, `tests/callisto/test_boundaries.py`, `docs/upstream-engine-manifest.json`, README 및 현황 문서

## 검증 결과와 브랜치 통합

검증된 코드 커밋은 `cb736d87490dadee2c142bedcfd43a357c8e5c5b`예요. 아래 네 CI 작업의 통과를 확인한 뒤 최종 보고서만 갱신하고 main/master를 fast-forward로 동기화해요. 보고서만 바꾸는 커밋에는 `[skip ci]`를 사용하며, 검증된 소스·테스트·패키징 코드는 변경하지 않아요.

- Work 실제 AI CLI/로그인/버전/Android 호출: **수행하지 않음**.
- 로컬 Linux 전체 오프라인: **2124 passed / 29 skipped / 8 deselected**, 89 warnings, 64.81초. skip에는 Work PID namespace 제한 17개와 Windows 전용 2개 및 기존 선택적 검사가 포함돼요. 일반 Linux CI에서 PID 관련 검사를 실행해요.
- lint(변경 코드 및 Callisto/tools/tests), `git diff --check`, `pip check`: 통과. 원본 핵심 32개 + 엔진/액션 23개 해시 일치.
- frontend 없는 wheel 빌드 통과. clean venv에서 Pro graph/config/SDK import, CLI help/version 및 checkout 밖 Skill install-update-status 통과. 기본 wheel의 APK 부재도 확인했어요. 이 Work 환경에는 Android SDK/JDK가 없어 APK 실빌드는 CI에서 수행해요.
- GitHub Actions [최종 코드 검증 실행 #6](https://github.com/cjftya/callisto_auto/actions/runs/39260184679): **success**. Work에서 실제 AI CLI를 실행하지 않았어요.

| CI 작업 | 결과 | 검증 범위 |
|---|---|---|
| Linux cli-regression | **2141 passed, 12 skipped, 8 deselected**, 89 warnings, 77.19초 | 전체 Pro 오프라인 회귀, lint, pip check, 기본 wheel clean 설치, checkout 밖 Skill 설치/업데이트/상태 |
| Windows cli-regression | **249 passed, 1 skipped**, 2 warnings, 13.90초 | CLI·프로세스 취소/timeout·내부 MCP·Helper 회귀, lint, pip check, 기본 wheel clean 설치와 Skill 설치 |
| Linux helper-build | **success** | 실제 Java/SDK APK 빌드, APK Signature v2/v3 검증, manifest/hash 검사, APK 포함 wheel clean 설치 |
| Windows helper-build | **success** | 동일 APK 빌드·서명·번들 검사 및 APK 포함 wheel clean 설치 |

Windows의 유일한 skip은 POSIX 전용 프로세스 검사예요. Windows 전용 fake 자식 트리 종료 검사는 실제 Windows CI에서 실행했어요. 첫 CI에서 새 테스트가 Windows 환경변수의 대소문자 alias를 POSIX와 같다고 가정한 부분을 수정했고, 위 최종 실행에서 통과했어요.

CI artifact:
- [Linux 기본 wheel·테스트 XML·wheel-report](https://github.com/cjftya/callisto_auto/actions/runs/39260184679/artifacts/12190506338)
- [Windows 기본 wheel·테스트 XML·wheel-report](https://github.com/cjftya/callisto_auto/actions/runs/39260184679/artifacts/12191305607)
- [Linux 개발용 APK·manifest·APK 포함 wheel](https://github.com/cjftya/callisto_auto/actions/runs/39260184679/artifacts/12190496085)
- [Windows 개발용 APK·manifest·APK 포함 wheel](https://github.com/cjftya/callisto_auto/actions/runs/39260184679/artifacts/12191050544)

각 APK는 같은 artifact의 manifest와 함께 사용해요. Actions artifact는 보존 기간이 있으므로 영구 release 배포와 구별해요.
- 미해결: 실제 Codex 모델/로그인/이미지/schema/tool 왕복, host 스킬 인식, Android 자연어 작업·탭/스크롤/입력·체크포인트/복구, 실제 timeout/취소·Windows native CLI 모두 사용자 PC 수용 검증이 필요해요.

## 공식 계약 참고 (2026-10-19 문서 확인)

- [Codex CLI 옵션](https://learn.chatgpt.com/docs/cli/reference): ignore-user-config는 사용자 config를 제외하되 CODEX_HOME 인증을 유지해요.
- [Codex 스킬 검색 경로](https://learn.chatgpt.com/docs/build-skills): 사용자 `~/.agents/skills`와 repo `.agents/skills`.
- [Claude API key 우선순위](https://support.claude.com/en/articles/12304248-manage-api-key-environment-variables-in-claude-code)
- [Claude 환경변수](https://code.claude.com/docs/en/env-vars)
