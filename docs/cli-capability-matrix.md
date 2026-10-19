> **v4.1 최신 결과:** [기능 보존·호환성·검증 보고서](cli-v4.1-report.md). 아래 v4 기록은 당시 상태예요. v4.1은 Native Explorer opt-in, 인증 환경 격리, 검증 누락 exit 2, 스킬 설치 명령 및 선택적 Helper 포함 wheel을 추가해요. 실제 AI CLI·Android 검증은 여전히 미완료예요.

# CLI capability matrix

2026-10-19. 공식 CLI와 기기가 연결된 선택된 실행 환경에서 승인된 실제 검증을 수행해요.
호스팅 앱 이름으로 CLI 실행을 금지하지 않아요. 오프라인 테스트는
`CALLISTO_FORBID_LIVE_CLI=1`을 명시적으로 설정해 실제 추론을 차단해요.
아래의 “오프라인 통과”는 fake CLI/모킹 결과이며 실제 모델의 호환성 증거가 아니에요.

| 기능 | Codex | Claude Code | Gemini CLI |
|---|---|---|---|
| 공식 비대화형 전송 | 구현, 실제 PC 검증 필요 | 실험 구현, 실제 PC 검증 필요 | 미구현 |
| 텍스트 / 역할 / 전체 이력 | 오프라인 통과 | 파서 구현, 미검증 | 미구현 |
| 이미지 | inline base64 → 임시 이미지 → `--image`, 오프라인 통과 | 명시적 미지원 오류 | 미구현 |
| JSON schema | envelope 및 도구 인자 로컬 검증, 오프라인 통과 | 동일 로컬 검증, 미검증 | 미구현 |
| ARTEMIS 도구 호출 | 실행하지 않고 name/ID/args 반환, 오프라인 통과 | 구조 구현, 미검증 | 미구현 |
| tool 결과 왕복 / 대화 이력 | 오프라인 통과 | 구조 구현, 미검증 | 미구현 |
| 부분 출력 / 프로세스 실패 | 완료 이벤트/종료 코드 확인, 오프라인 통과 | success subtype/종료 코드 확인 | 미구현 |
| 타임아웃 / 비동기 취소 | Linux fake 자식 그룹 정리 테스트 통과 | 공통 프로세스 전송 사용 | 미구현 |
| Windows 자식 트리 정리 | fake 트리 회귀 추가, CI 결과는 migration-status 참조. 실제 공급자는 미검증 | 공통 fake 트리 회귀 추가, CI 결과는 migration-status 참조. 실제 공급자는 미검증 | 미구현 |
| 실제 계정 인증 / 추론 | 사용자 PC에서 수행 예정 | 사용자 PC에서 수행 예정 | 미구현 |
| Android E2E | 사용자 PC에서 수행 예정 | 이미지 전송이 없어 대상 아님 | 미구현 |

## 구조화 도구 호출 방식

CLI 자체가 Android 액션을 수행하지 않아요. CLI 출력은 `{content, tool_calls}` JSON envelope예요.
`tool_calls`의 `args_json`을 파싱하고 기존 도구 JSON Schema로 검증한 뒤 LangChain `AIMessage.tool_calls`로 반환해요.
실제 호출과 도구 결과 처리는 기존 ARTEMIS 그래프가 수행해요. CLI의 내장 shell/MCP tool 실행을 ARTEMIS 도구 호출과 혼동하지 않아요.

## native Gemini 및 기능 차이

- Google SDK의 `types` 데이터 구조만 남기고, 에이전트의 SDK Client 생성은 Callisto 로컬 native port로 연결했어요.
- native 텍스트·이미지·function declarations/response 및 JSON schema 호환 포트를 구현했어요. 모델 추론은 공통 CLI 어댑터를 통과해요.
- native Files upload/get/list/delete, Interactions/agentic video, 명시적 cloud context cache, 음성 블록, server-side search는 미지원이며 명시적 오류예요. fake cloud URI, 가짜 토큰 수 또는 성공 결과를 만들지 않아요.
- CLI 설정은 원본의 기존 Universal Explorer/영상 프레임 경로를 사용해요. 해당 경로는 원래 ARTEMIS의 구현이고 에이전트를 새 반복 루프로 재작성하지 않았어요. 실제 native 경로와의 의미·정확도 동등성은 미확인이에요.
- 기본 설정의 Google 검색 grounding은 활성화하지 않았어요. `enable_grounding=true`로 요청하면 조용히 무시하지 않고 오류를 반환해요.
- Google 모델별 thinking budget, 원시 thought signature, 캐시 사용량은 CLI의 동일 기능이라고 간주하지 않아요. 실제 CLI가 반환한 usage만 기록해요.
- 일반 CLI 모델로 변경된 object detector의 정밀 좌표 인지 정확도는 실제 기기에서 확인해야 해요.
- OCR은 선택적 CLI 이미지 포트로 교체했어요. Google Vision API를 직접 호출하지 않아요. `CALLISTO_OCR=1`의 정확도·지연은 실제 검증 전이에요.

## 실제 PC의 수용 검증

`python tools/verify_local_cli.py --allow-live-cli`는 텍스트, schema, 도구 인자,
도구 결과 왕복, 대화 이력, 이미지 색상 인지를 실제 CLI로 확인해요.
결과는 `traces/local-cli-acceptance.json`으로 저장해요. 이후 Android 기기 테스트,
실제 공급자 실패·취소·긴 입력 및 Windows 프로세스 정리 검증도 필요해요.
현재 P0의 실제 공급자 동등성 검증과 P5의 Android E2E를 통과했다고 주장하지 않아요.

공식 인터페이스 참고:
- https://learn.chatgpt.com/docs/non-interactive-mode
- https://code.claude.com/docs/en/headless
- https://geminicli.com/docs/cli/headless/

## v4 경계 및 배포 제한

- API 키 환경 변수는 Explorer/영상 엔진을 선택하지 않아요. 기본 경로는 기존 Universal 프레임/이미지 엔진이에요.
- 직접 API 공급자는 모두 거부해요. 레거시 Settings 키 getter는 항상 None이고 키 저장/ADC 검증은 명시적으로 거부해요.
- Codex의 shell/apps/plugins/hooks/subagent/search 기능을 끄는 명령을 구성해요. 공급자 자체 도구 실행 이벤트가 발견된 응답도 실패로 처리해요.
- 공식 CLI 플래그를 문서와 대조했지만 실제 설치 버전별 호환성, 로그인, 정확도는 사용자 PC 확인이 필요해요.
- CLI Skill과 Helper 버전 manifest는 wheel에 들어가요. APK 바이너리는 없으므로 번들 Helper 설치는 검증하지 않았어요.
- 내부 액션 세션은 mcp v1 API를 사용하므로 `mcp>=1.26,<2`를 유지해요. 설치된 Google SDK는 데이터 타입 용도이며 직접 Client 생성은 활성 소스에 없어요.
- 과거 진단 ID (`gemini_api_key`, `vision_ocr_key`)와 서버 경로 상수는 저장된 보고서/import 호환용이에요. 외부 서버를 실행하지 않아요.

## Helper 접근성 진단 수정 — 2026-10-19

- Android의 축약형(`com.artemis.helper/.ArtemisAccessibilityService`)과 전체형
  (`com.artemis.helper/com.artemis.helper.ArtemisAccessibilityService`)을 같은 서비스로 인식해요.
  상태 조회, 활성화, 재연결, 삭제 모두 같은 비교를 사용해요.
- 수정 전 연결 기기에서 Android 접근성 설정은 전체형으로 활성화돼 있었고,
  Helper 응답은 버전 코드 6 / 프로토콜 2였어요. 문자열 비교 때문에 Callisto만 비활성화로 오판했어요.
- 수정 후 같은 기기(`R3CY50L9M6K`)의 `callisto helper status --json`에서
  `enabled`, `reachable`, `protocol_supported`가 모두 true로 확인됐어요.
- Windows / Python 3.13 오프라인 전체 회귀: **2158 passed, 7 skipped, 8 deselected**.
  Helper 모의 회귀 54개에 전체형/축약형 감지, 중복 등록 방지, 다른 서비스 보존 검사가 포함돼요.
- 이 진단은 실제 AI 추론이나 Android 배터리 탐색 E2E 성공 증거가 아니에요.

## v4.2 — inference boundary and setup

| Area | Implemented contract | Evidence / limit |
|---|---|---|
| Image transport | balanced/quality/economy/off; actual PNG/JPEG/WebP MIME; stored-pixel EXIF handling; alpha/RGB conversion; bounded cache and request limits | Offline image boundary tests; real small-text accuracy is unverified |
| Coordinates | Pro normalized coordinates unchanged; opt-in CLI OCR pixel polygons inverse-mapped and bounds checked | Portrait/landscape/foldable/tall frame roundtrip tests; device acceptance pending |
| Repeated context | Exact duplicates share an attachment index, with all message/tool references preserved; off keeps duplicates | Distinct historical evidence is not discarded; existing Transcript summaries/scrub/recall preserved |
| Setup | setup.ps1/setup.sh; setup/check/repair; user settings precedence; native discovery; official login status; explicit device selection; managed Skill preservation | Offline fake-process/config tests and isolated wheel imports; fresh Windows/real device validation pending |
| Helper | Setup refuses hash mismatch or undeclared/old protocol; build emits protocol_version; selected-device lock around provisioning | APK-free distribution reports fallback. Legacy helper/ APK is outside canonical bundle and mismatches manifest |
| Usage | Actual CLI usage, image metrics, elapsed time, agent/stage aggregation; unknown remains null; no cache double counting | compare_usage.py compares paired real run reports; no paid inference baseline was captured in Work |
| Git | CI push trigger uses main only | Remote master deletion requires a Git-authenticated client or signed-in GitHub browser; not claimed complete |

See [v4.2 verification report](cli-v4.2-report.md) and [setup guide](advanced-setup.md).
