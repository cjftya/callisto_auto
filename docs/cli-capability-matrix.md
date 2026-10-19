# CLI capability matrix — P0 미통과

검사일: 2026-10-19 (Asia/Seoul). 환경: Linux, Python, Codex CLI 0.159.2.

| 항목 | Codex | Claude Code | Gemini CLI |
|---|---|---|---|
| 실행 파일 | `/opt/codex/bin/codex` 확인 | PATH에서 발견 안 됨 | PATH에서 발견 안 됨 |
| 공식 로그인 상태 | `Logged in using ChatGPT` 표시 | 미검증 | 미검증 |
| 실제 텍스트 추론 | 응답 없음, 45초 timeout | 미검증 | 미검증 |
| 이미지 입력 | 미검증 | 미검증 | 미검증 |
| JSON schema | 미검증 | 미검증 | 미검증 |
| ARTEMIS tool call 반환 | 미검증 | 미검증 | 미검증 |
| 여러 턴 문맥 | 미검증 | 미검증 | 미검증 |
| 취소/timeout | 실행 제한 확인, 공급자 취소 미검증 | 미검증 | 미검증 |
| 전체 P0 | **실패/차단** | 미검증 | 미검증 |

실행 중 featured plugin 요청에 `401 Unauthorized`와
`Could not parse your authentication token. Please try signing in again.` 경고가 관측됐어요.
이는 플러그인 요청의 인증 오류이며, 모델 API의 인증 실패가 직접 확인된 것은 아니에요.
실제 모델 응답 JSONL이 없어서 추론 경로의 정상 작동도 확인하지 못했어요.
네트워크·호스트 CLI 실행 환경·인증 중 정확히 무엇이 모델 응답을 막는지는 미확정이에요.

점검 도구는 인증 오류가 출력에 관측되면 `authentication_failed`로 분류해요.
이 상태는 인증 오류가 관측됐다는 뜻이며 모델 요청의 최종 원인 진단을 보장하지 않아요.
실행 파일 미설치, 프로세스 실패, 잘못된 출력, timeout은 각각 구분해요.

`codex exec --help`에서 `--image`, `--json`, `--output-schema`, `resume` 옵션의 존재를
확인했지만, 옵션 존재를 기능 검증 결과로 사용하지 않았어요.
공식 문서: https://developers.openai.com/codex/noninteractive

## 다시 진행할 조건

1. 정상적으로 로그인되고 모델 추론이 가능한 로컬 CLI 환경에서 텍스트 점검 성공.
2. 이미지 인지, schema 검증, tool call ID/이름/인자 및 tool 결과 왕복 검증.
3. 여러 턴 문맥, 긴 입력, timeout, 취소 및 프로세스 종료 검증.
4. 지원 CLI를 하나 선정하고 증거를 남긴 뒤 P1 이관 시작.

외부 API 키 호출이나 토큰 추출로 우회하지 않아요. 합성 응답/모킹 테스트로
실제 공급자 호환성 검증을 대체하지 않아요.
