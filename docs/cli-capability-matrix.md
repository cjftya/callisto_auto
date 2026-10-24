# CLI 지원 범위

Antigravity CLI (`agy`) supports host registration, explicit selection and managed Skill removal.
Global directory: `~/.gemini/antigravity-cli/skills/callisto/` (separate from IDE/app).
Pro inference with `--ai-cli antigravity` is UNSUPPORTED pending validated non-tool image
input, complete tool blocking, structured output/usage and Android E2E. No provider fallback.
Antigravity 수용 조건은 공식 비도구 이미지 입력·도구 차단 및 Android 실기기 검증임.

현재 `main` 기준. 구조는 [아키텍처](architecture.md), 실제 설치·설정은 [고급 가이드](advanced-setup.md) 참조. 아래 구현·오프라인 계약 검사와 실제 공식 CLI·Android 수용 결과는 구분됨.

| 기능 | Codex | Claude Code | Gemini CLI |
| --- | --- | --- | --- |
| 비대화형 전송 | JSONL | JSON 출력 + stream-json 입력 | stream-json |
| 텍스트·이력·도구 응답 데이터 | 구현·오프라인 검사 | 구현·오프라인 검사 | 구현·오프라인 검사 |
| 스크린샷 | `--image` | base64 멀티모달 입력 | `@절대경로` 첨부 |
| 결과 검증 | 완료 이벤트 + schema | `--json-schema` + 로컬 schema | 완료 이벤트 + 로컬 schema |
| CLI 자체 도구 제한 | read-only, shell/apps/MCP 등 차단 | `--tools ""`, MCP 차단 | plan mode, deny 정책, 도구 이벤트 검사 |
| 모델·추론 수준 | 공식 CLI 사용자 기본값 | 공식 CLI 사용자 기본값 | 공식 CLI 사용자 기본값 |
| 스킬 경로 | `~/.agents/skills` | `~/.claude/skills` | `~/.gemini/skills` |
| 실제 버전·인증·시각 인지·Android E2E | 선택된 실행 PC 검증 필요 | 선택된 실행 PC 검증 필요 | 선택된 실행 PC 검증 필요 |

구현된 공급자 목록과 현재 PC에서 실행 가능한 launcher는 다름. `doctor`는 경로·설정을 검사하며 모델 CLI를 실행하지 않음. `setup check`는 발견한 CLI별 스킬·준비 상태를 구분하고 Codex의 공식 로그인 상태를 조회할 수 있음. `READY`도 모델 추론·Android 성공을 의미하지 않음. 호스트 대화의 일시적인 모델 선택은 별도 자식 CLI에 자동 상속되지 않음.

## Pro 및 데이터 경계

자동 탐색의 Setup은 지원 호스트 중 하나의 launcher·Skill·확인된 인증 상태가 준비되고 공통 Python·ADB·Helper 조건이 충족되면 `READY`임. 나머지 호스트 문제는 `clis.<host>.issues` 및 `warnings`에 남김. Doctor는 launcher·설정·ADB 경로만 확인하며 Skill·로그인·기기 연결을 검사하지 않음. 두 명령 모두 `ready_providers`, `unsupported_hosts`를 제공하고 Antigravity만 있거나 명시적으로 선택하면 `UNSUPPORTED`(종료 코드 2), 사용 가능한 지원 호스트가 없으면 `ACTION_REQUIRED`(1)임. 혼합 환경의 Antigravity는 준비된 지원 호스트를 차단하지 않음. `READY`는 추론·실기기 성공 증거가 아님.

| 영역 | 현재 지원 계약 | 한계 |
| --- | --- | --- |
| Pro | 원본 그래프·프롬프트·도구 schema·검증·재시도·복구·체크포인트·메모리 유지 | mock 성공을 실제 모델 동등성으로 간주하지 않음 |
| 구조화 도구 | `{content, tool_calls}` 응답을 schema 검사 후 기존 Pro가 실행 | CLI 자체 shell/MCP 실행 이벤트는 실패 처리 |
| Explorer·영상 | 기존 Universal 경로 기본, `CALLISTO_EXPLORER_ENGINE=native` opt-in 포트 | native Files/Interactions/agentic video 동등성 보장 없음 |
| native 데이터형 | `google.genai.types` 호환, 추론은 공통 CLI 어댑터 | SDK Client·직접 AI API 호출 없음 |
| 미지원 native 기능 | Files, Interactions, 명시적 cloud cache, 음성, server-side search 요청은 명시적 오류 | 가짜 cloud URI·성공·토큰 수 생성 없음 |
| OCR | `CALLISTO_OCR=1` opt-in, CLI 이미지 포트와 원본 픽셀 역변환 | 실제 좌표·작은 글씨 정확도는 기기 검증 필요 |
| 이미지 | balanced/quality/economy/off, MIME·저장 픽셀·EXIF·범위 검사, 동일 첨부 중복 제거 | 원본 캡처·XML·Trace·Pro 정규화 좌표 유지; 절감률 미확인 |
| usage | 실제 CLI 토큰·이미지·시간·단계 집계 | 알 수 없는 값은 null; cached input 이중 합산 없음 |
| 판정 | 0 PASS / 1 FAIL / 2 INCOMPLETE / 130 CANCELLED | 결과 JSON 및 원본 Trace 확인 필요 |

## 설치·호환성

- Windows PowerShell·Linux bootstrap과 setup/check/repair, 자동 다중 호스트 스킬 등록 구현됨. 스킬 실행은 현재 호출 호스트를 명시함.
- Setup `READY`의 다음 실행 안내는 실제 `ready_providers`의 CLI 이름만 표시함. 미지원·준비 미완료 호스트는 제외하며 오류 상태에서는 기존 원인별 조치 안내와 종료 코드 유지됨.
- ZIP 설치는 스크립트 위치의 `.venv`와 두 파일의 글로벌 Skill 등록을 사용함. 설치 후 폴더 이동·이름 변경은 지원하지 않으며 새 위치에서 `.venv` 재생성·Setup 재실행이 필요함. 경로·재등록 오프라인 검증은 실제 기기 설치 성공과 구분함.
- 소스 설치의 `uninstall.ps1` / `uninstall.sh`는 미리보기·명시적 승인 후 해당 설치 전체와 연결된 관리 Skill을 제거함. 외부 시스템 Python 작업자가 런처 종료를 기다리고 결과 JSON을 기록함. 공유 설정은 기본 보존하며 별도 옵션·검증이 필요함. 커스텀 설정·사용자 수정 Skill·다른 설치·기기의 Helper는 보존함. 실제 사용자 PC에서의 제거 동작은 별도 검증 대상임.
- setup의 `adb devices` 출력은 UTF-8 및 대체 문자로 디코딩함. ADB 미설치·실행 실패·시간 초과와 기기 미연결·unauthorized·offline 안내를 구분함. Windows Python 3.13/CP949 오프라인 회귀는 통과했으며 실제 기기 연결 검증과 구분함.
- Windows는 native 실행 파일 또는 확인된 npm JS 엔트리포인트를 사용함. 필요한 옵션을 거부하는 구버전 CLI에 안전 옵션을 빼고 재시도하지 않음.
- Helper는 APK·manifest 해시·버전·프로토콜을 확인하고 선택 기기 락을 사용함. canonical APK 미포함 배포는 기존 호환 Helper 또는 UIAutomator2 fallback 사용함.
- canonical 소스와 해당 소스로 빌드한 wheel에는 CI에서 생성한 개발 서명 Helper APK·대응 manifest가 포함됨. APK/manifest 해시·버전·프로토콜 검증과 실제 기기 설치 성공은 구분함. [GitHub Actions](https://github.com/cjftya/callisto_auto/actions/workflows/offline.yml)에서 커밋별 빌드 결과 확인 가능함.
- 내부 in-process MCP, Explorer `flash` tier, 공유 summarizer/compressor, SDK 공개 import는 보존됨. 웹 UI·HTTP Daemon·외부 MCP·독립 Flash 실행 프로필은 지원하지 않음.
- 원격 SDK는 import 호환용이며 Callisto 원격 서버 제공을 의미하지 않음. 기존 진단 ID·경로·`artemis` 별칭 유지됨.

## 실제 수용 검증

공식 CLI와 Android가 준비된 실행 PC에서 명시적으로 수행함. 이번 정리에서는 실행하지 않음.

```sh
python tools/verify_local_cli.py --allow-live-cli --ai-cli codex
callisto run "설정 앱의 배터리 화면 확인" --ai-cli codex --device-serial SERIAL --verification-level final
callisto trace list
```

공급자별 로그인·긴 입력·이미지·다중 턴·timeout·취소, Windows 프로세스 종료, Android 조작·검증·복구를 확인해야 함. 오프라인 회귀 결과와 실제 기기·모델 수용 검증은 별도로 구분함.

## Operator A/B 최적화의 검증 경계

| 기능 | 세 공급자 공통 구현 | 운영 조건 |
| --- | --- | --- |
| usage 정규화 | raw + normalized + scope; unknown은 null, 누계는 합계 제외 | 설치된 CLI 버전의 실제 fixture 확인 필요 |
| Context IR / Shadow | 메시지 순서·tool pair·status·영역 계측, 실제 입력 유지 | 기본 off |
| Ready-only view | 기존 ready capsule의 연속 prefix, 최근 raw floor 유지 | `ready_only` 명시 선택, 실제 정확도 미검증 |
| Evidence / pin | 현재·조회·비교 증거와 geometry 보존, 명시적 해제 | 자동 incident/판단 완료 해제는 미연결; 한도 초과 시 오류 |
| ToolMessage status | IR에는 항상 기록, opt-in 송신에 success/error 추가 | off/shadow 송신 형식 유지 |
| 세션 재사용 | 미구현 | 이번 범위 제외 |

합성 replay의 바이트 감소와 가짜 CLI 성공은 실제 토큰/과금/행동 정확도의 증거가 아니다.
Windows 경로·launcher 계약 회귀와 실제 Windows 호스트 실행 결과도 별도로 구분한다.
