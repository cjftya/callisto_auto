# CLI capability matrix

2026-10-19. 사용자의 실행 범위 수정에 따라 **Work 내부 AI CLI 실행은 금지**해요.
이전 중첩 실행 실패는 대상 PC의 CLI 지원 여부를 판정하는 근거가 아니에요.
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
| 타임아웃 / 비동기 취소 | Linux 자식 그룹 정리 테스트 통과 | 공통 프로세스 전송 사용 | 미구현 |
| Windows 자식 트리 정리 | 구현, 대상 Windows 미검증 | 공통 구현, 대상 Windows 미검증 | 미구현 |
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
도구 결과 왕복, 대화 이력, 이미지 색상 인지를 실제 CLI로 확인해요. **Work에서는 실행하지 않아요.**
결과는 `traces/local-cli-acceptance.json`으로 저장해요. 이후 Android 기기 테스트,
실제 공급자 실패·취소·긴 입력 및 Windows 프로세스 정리 검증도 필요해요.
현재 P0의 실제 공급자 동등성 검증과 P5의 Android E2E를 통과했다고 주장하지 않아요.

공식 인터페이스 참고:
- https://learn.chatgpt.com/docs/non-interactive-mode
- https://code.claude.com/docs/en/headless
- https://geminicli.com/docs/cli/headless/
