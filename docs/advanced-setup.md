# 고급 설치·운영 가이드

Antigravity CLI (`agy`) supports host registration, explicit selection and managed Skill removal.
Global directory: `~/.gemini/antigravity-cli/skills/callisto/` (separate from IDE/app).
Pro inference with `--ai-cli antigravity` is UNSUPPORTED pending validated non-tool image
input, complete tool blocking, structured output/usage and Android E2E. No provider fallback.
구체적인 지원 조건은 [CLI 지원 범위](cli-capability-matrix.md)를 기준으로 함.

Google ARTEMIS의 **기존 Pro 그래프·에이전트는 유지**하고, 모델 통신을 인증된 로컬 AI CLI로 연결하는 Android 자동 테스트 도구예요.

현재 구조와 지원 판정은 [아키텍처](architecture.md) 및 [지원 범위](cli-capability-matrix.md)를 기준으로 해요. 실제 CLI 모델 호환성과 Android E2E는 공식 CLI와 기기가 연결된 실행 환경에서 확인해야 해요.

## 로컬 PC 설치

Python 3.12 이상, Android Platform Tools(ADB), 사용할 공식 AI CLI(Codex·Claude Code·Gemini CLI)의 설치와 로그인이 필요해요.

Linux:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
callisto doctor --json
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
callisto doctor --json
```

`doctor`는 실행 파일과 설정만 검사해요. AI CLI를 실행하거나 인증·추론 성공을 주장하지 않아요.
AI CLI 로그인은 해당 CLI의 공식 절차로 사용자 PC에서 수행하세요. API 키나 로그인 토큰을 Callisto에 복사하지 않아요.

## 사용자 PC에서만 수행하는 검증과 실행

```sh
# 실제 모델을 호출하는 명시적 수용 검증
python tools/verify_local_cli.py --allow-live-cli --ai-cli codex
adb devices
callisto run "설정 앱에서 배터리 화면을 열고 배터리 항목이 표시되는지 확인" --ai-cli codex --device-serial SERIAL
callisto trace list
```

실행은 웹 UI·HTTP Daemon·외부 MCP 서버 없이 로컬 Pro 그래프로 진행돼요.
동일 호스트 AI의 현재 대화 세션을 재사용하는 방식은 아니며, 매 호출마다 기존 에이전트의 메시지 이력을 별도 CLI 프로세스로 전달해요.

`callisto run`은 세션 ID와 결과 JSON 경로를 출력해요. 원본 Trace, 체크포인트와 `run_outcome.json`을 함께 확인하세요.
종료 코드: **0 검증 통과 / 1 작업·검증 실패 / 2 검증 누락·미확정 / 130 취소**예요. `test_status=not_reported`도 2로 종료하고, 출력과 결과 JSON에 같은 `exit_code`를 기록해요. 잘못된 검증 요약도 성공으로 처리하지 않아요.

## AI CLI 연결과 기능 범위

- Codex: 초기 구현 대상. 텍스트·이미지·JSON·도구 호출 반환·여러 턴 메시지 전달을 모의 테스트로 검증했어요. 특정 모델을 선택하지 않고 CLI의 자체 기본값을 사용해요.
- Claude Code: stream-json multimodal image 입력, JSON Schema 출력, 실행 도구 차단 경로를 구현했어요. 실제 설치 버전과 인증·스크린샷 정확도는 로컬 검증이 필요해요.
- Gemini CLI: @이미지 파일 입력, stream-json 완료 이벤트 파싱, 읽기 전용 모드와 도구 차단 정책을 구현했어요. 실제 CLI가 이 입력/정책을 올바르게 지원하는지는 로컬에서 확인해야 해요. Google 원본의 native Files/Interactions/명시적 캐시·음성·검색 기능은 별도이며 지원을 보장하지 않아요.
- 기존 Universal 영상 분석의 프레임/이미지 경로는 유지했어요. 실제 영상·음성 기능 전체가 동등하다고 주장하지 않아요.
- 선택적 OCR은 `CALLISTO_OCR=1`로 켜면 CLI 이미지 추론을 사용해 원래 텍스트/좌표 형식을 반환해요. 기존 Vision API 키로 자동 활성화하지 않아요. 실제 좌표 정확도 검증은 별도로 필요해요.

Codex 실행 파일은 `CALLISTO_CODEX_EXECUTABLE`로 지정할 수 있어요. Callisto는 모델명과 추론 수준을 강제로 지정하지 않아요. Codex 호출은 사용자 CLI 설정과 공식 인증을 사용하며, 임시 디렉터리·read-only sandbox·JSON 출력으로 동작해요. 관리자가 강제한 정책은 우회하지 않아요.
자식 프로세스에는 주요 공급자의 API Key 및 해당 공급자의 대체 API 엔드포인트/라우팅 환경변수를 전달하지 않아요. 부모 환경과 공식 로그인 저장소는 변경하지 않아요. `HOME`/`USERPROFILE`/`CODEX_HOME`/`CLAUDE_CONFIG_DIR` 및 공식 CLI OAuth 환경은 정상 상속해요. Callisto는 인증 파일이나 토큰을 추출하지 않아요. CLI에 저장된 로그인 종류 자체는 검사하지 않으므로, 사용자 PC에서 공식 계정 로그인을 준비해야 해요.

Windows에서 npm launcher를 직접 셸로 실행하지 않아요. Codex는 공식 native `.exe`를 탐색하며 Claude·Gemini는 검증된 npm JS 엔트리포인트를 설치된 Node로 실행해요. 적절한 엔트리포인트가 없으면 명시적으로 실패해요. 오래된 CLI가 필수 옵션을 거부하면 업데이트 안내와 함께 실패하며, 안전 옵션을 빼고 재시도하지 않아요. 실제 버전별 호환성은 미검증이에요.

`CALLISTO_EXPLORER_ENGINE=native`로 원래 Native Explorer 루프를 CLI 호환 포트에 연결할 수 있어요. 기본은 기존 Universal 경로예요. Native 모드도 이미지·함수 호출·원래 결과 검증을 유지하지만, Files/명시적 Context Cache는 지원하지 않아요. `ARTEMIS_USE_FILE_API=true`나 명시적인 캐시 요청은 오류예요. 기본 캐시는 사용하지 않고 전체 이력을 전달해요. 원시 thought signature, 공급자 전용 thinking budget과 안전 설정의 동등성은 보장하지 않아요.

Google 전용 모델(예: Robotics ER)의 공간 인지 정확도와 일반 CLI 모델의 결과가 같다고 보장하지 않아요.

## 오프라인 개발

```sh
CALLISTO_FORBID_LIVE_CLI=1 python -m pytest
python -m pip install wheel setuptools
python -m pip wheel --no-deps --no-build-isolation -w dist .
```

자동 테스트는 실제 AI CLI 실행을 금지해요. 모의 응답과 가짜 Python 실행 파일만 사용해 계약, 취소와 프로세스 정리를 검증해요.
브라우저 UI, 관리자 콘솔, 외부 MCP, Flash 실행 전용 원본 테스트는 `tests/upstream_removed/`에 보관하고 기본 테스트에서 제외했어요. Pro가 공유하는 내부 MCP 액션 세션, Flash 폴더의 요약/압축 코드와 Explorer `flash` tier는 유지했어요.

## 스킬 설치 및 업데이트

wheel은 프런트엔드 없이 설치되고, 정식 스킬 원본을 함께 배포해요. `setup.ps1` / `setup.sh` 실행 시 사용 가능한 Codex·Claude·Gemini를 탐색해 각 호스트의 스킬 경로(`~/.agents/skills/callisto`, `~/.claude/skills/callisto`, `~/.gemini/skills/callisto`)에 자동 등록해요. 수동 설치도 별도 CLI 선택 없이 실행할 수 있어요. pip 설치만으로는 사용자 홈을 변경하지 않아요.

```sh
callisto skill install
callisto skill status
# 패키지 업데이트 후
callisto skill update
# 선택 사항: 특정 CLI만 복구
callisto skill install --ai-cli claude
```

`--directory <스킬 상위 폴더>`로 별도 경로도 지정할 수 있지만 여러 CLI를 탐색한 경우 경로 충돌 방지를 위해 `--ai-cli`로 하나를 지정해야 해요. CLI를 찾지 못하면 설치를 진행하지 않고 설치 안내를 출력해요. 패키지 버전·내용 해시·설치 상태를 기록하고, 사용자가 수정한 파일이나 기존의 관리되지 않는 스킬은 덮어쓰지 않아요. 실행 중인 AI CLI에 스킬이 나타나지 않으면 재시작하세요. 이 명령은 파일 경로만 검증하며 실제 호스트 인식 여부는 사용자 PC에서 확인해야 해요.

## Helper 빌드와 배포

기본 canonical 번들과 이 소스로 빌드한 wheel에는 CI에서 생성한 Helper APK와 대응 manifest가 포함돼요. `setup`은 `packages/artemis-accessibility-helper/`의 번들을 검증하고 선택 기기에 설치해요. 저장소 루트 `helper/`의 과거 APK는 현재 번들이 아니에요. APK를 제외한 배포에서는 기존 호환 Helper를 확인하고, 없으면 `auto` 계층 모드에서 UIAutomator2로 fallback해요. 실제 기기 설치·호환성은 별도 검증이 필요해요.

Linux/Windows 모두 JDK 17과 Android SDK Platform 35/Build Tools 35.0.0을 준비하면 셸 스크립트 없이 빌드할 수 있어요.

```sh
python tools/build_helper.py --sdk <Android-SDK-경로>
callisto helper bundle-status
# 빌드한 APK와 해당 manifest를 함께 포함하는 wheel
python -m pip wheel --no-deps --no-build-isolation -w dist .
```

`helper-build` CI는 두 OS에서 개발용 APK/manifest와 APK 포함 wheel을 빌드해 Actions artifact로 제공해요. 이는 기존 debug 서명을 사용하는 개발 빌드이며 production release는 아니에요. 빌드·서명·독립 wheel 설치의 성공 여부는 [Actions 실행 결과](https://github.com/cjftya/callisto_auto/actions/workflows/offline.yml)에 구분해서 기록해요.

별도 APK를 사용할 때는 **APK와 일치하는 `helper_manifest.json`을 같은 폴더에** 두고 `CALLISTO_HELPER_DIR`로 지정하세요. `callisto helper bundle-status`는 기기 접근 없이 경로/버전/SHA-256을 검사해요. 패키지·버전·해시가 맞지 않는 번들은 설치하지 않아요. `callisto helper status --serial SERIAL --json`은 사용자 PC에서 설치 버전과 응답 프로토콜을 확인해요. 이미 설치된 앱을 강제로 다운그레이드하지 않아요.

- [현재 아키텍처](architecture.md) · [CLI 지원 현황](cli-capability-matrix.md)
- [원본 보존 기준](upstream-baseline.md)
- [CLI Skill](../skills/callisto/SKILL.md)
- [라이선스](../LICENSE), [제3자 고지](../third_party/mobile_use/NOTICE)

## 원클릭 설정과 우선순위

Windows는 `setup.ps1`, Linux는 `setup.sh`가 동일한 표준 라이브러리 bootstrap을 사용해요. Python 3.12+ 가상환경을 재사용하고, 소스 fingerprint가 달라지거나 설치가 없을 때만 pip 설치를 다시 해요. 매번 pip check와 CLI 도움말을 확인하고 setup을 이어서 실행해요. 실패 후 같은 명령으로 재개해요. 오래된 Python으로 만든 `.venv`는 자동 삭제하지 않고 명확히 실패해요.

Windows `-Check` / Linux `--check`는 설치·설정 파일을 변경하지 않아요. 기본 설치에서는 사용 가능한 모든 AI CLI에 스킬을 등록하고, CLI를 별도로 고르지 않아요. `--ai-cli` / `-AiCli`는 특정 CLI만 점검·복구할 때 선택적으로 사용해요. Windows `-NonInteractive`, Linux `--non-interactive`는 입력을 요구하지 않고 JSON 결과를 반환해요. 여러 기기는 명시적으로 `-DeviceSerial SERIAL` / `--device-serial SERIAL`을 선택해요. 공식 로그인은 각각의 CLI에서 진행하고, USB 디버깅은 사용자 승인으로 처리해요. 원클릭 설정이 실제 AI 수용 검증을 실행하지 않아요.

```powershell
.\setup.ps1 -Check -NonInteractive
.\.venv\Scripts\python.exe -m callisto.cli setup check --json
.\.venv\Scripts\python.exe -m callisto.cli setup repair --device-serial SERIAL
```

설정 파일은 Windows `%LOCALAPPDATA%/callisto/settings.json`, Linux `$XDG_CONFIG_HOME/callisto/settings.json` (기본 `~/.config/callisto/settings.json`) 한 곳이에요. `CALLISTO_CONFIG`로 파일 위치를 바꿀 수 있어요. 파일에는 image_policy/device_serial과 CLI 실행 파일 경로만 저장해요. 설치 과정에서는 CLI 선택을 저장하지 않아요. 스킬이 실행할 때 호출 호스트를 `--ai-cli`로 전달하며 이전 버전이 저장한 `provider` 값은 무시하고 재저장 시 정리해요. 비밀정보·인증은 저장하지 않아요.

| 설정 | 실행 옵션 | 환경변수 | 내장 기본값 |
|---|---|---|---|
| 이미지 | `--image-policy` | `CALLISTO_IMAGE_POLICY` | `balanced` |
| 기기 | `--device-serial` | `CALLISTO_DEVICE_SERIAL` | 준비된 기기 1대일 때 자동 선택 |
| CLI 호스트 | `--ai-cli` | `CALLISTO_AI_CLI` | 설치·스킬 명령은 전체 자동 탐색, `run`은 단일 CLI일 때만 자동 식별 |
| CLI 실행 파일 | 공급자별 실행 파일 설정 | `CALLISTO_CODEX_EXECUTABLE` 등 | PATH 및 공식 실행 파일 탐색 |

우선순위는 실행 옵션 > 명시 환경변수 > 사용자 설정 > 기본값이에요. 기존 `config/artemis.jsonc`의 에이전트 구성·기능 설정은 유지해요. 기존 노드별 모델·추론 값은 내부 호환용으로만 보존하며 실제 CLI 호출에는 전달하지 않아요. 이전 버전의 저장된 모델 설정도 무시하고 재저장 시 정리해요. setup은 이 파일을 수정하지 않아요. 잘못된 사용자 설정은 보존하고 실패를 알려요.

`doctor`는 provider CLI를 실행하지 않는 경로·설정 검사예요. 설정 시 `setup check --json`은 탐색된 각 CLI의 설치·스킬 상태를 `clis`·`skills`로 반환해요. `setup check`는 Codex에 대해 공식 `codex login status`로 로그인 상태를 확인하되 출력과 인증 파일을 수집하지 않아요. `--skip-login-check` 또는 `CALLISTO_FORBID_LIVE_CLI=1`에서는 이를 생략하고 미확인 상태로 표시해요. 로그인 성공 여부만으로 특정 모델의 추론 성공이나 구독 인증 종류를 보장하지 않아요.

setup repair는 사용자 수정 스킬을 덮어쓰지 않아요. Helper 설치는 명시 선택/유일한 준비 기기에만 수행하며 기존 작업의 기기 락을 획득할 수 없으면 중단해요. APK를 직접 빌드하지 않는 일반 설치에는 JDK·Android SDK 빌드 도구가 필요 없고, 기기 연결용 ADB는 필요해요. APK가 제외된 배포는 fallback을 표시해요. 저장소 `helper/`의 기존 APK는 기본 번들 위치가 아니며, 현재 manifest 해시와도 불일치하므로 복사해서 설치하면 안 돼요. CI의 같은 빌드에서 생성한 APK·manifest·wheel을 함께 사용하세요.

## 이미지 안전 경계와 계측

| 정책 | 긴 변 제한 | JPEG 품질 |
|---|---:|---:|
| balanced | 1920 | 80 |
| quality | 2560 | 90 |
| economy | 1440 | 75 |
| off | 원본 | 변환 없음 (EXIF 회전 정보는 제거) |

실제 PNG/JPEG/WebP 바이트를 검사하고 전송 MIME을 맞춰요. 투명도는 흰 배경에 합성하고 색 모드를 RGB로 맞춰요. EXIF 표시 회전은 적용하지 않고 제거해서 캡처의 저장 픽셀 좌표계를 유지해요. ICC 프로파일 기반 색 정확도는 보장하지 않아요. 정규화 좌표는 그대로 유지하고, CLI OCR의 픽셀 좌표는 전송 크기에서 원본으로 역변환하며 범위를 검사해요. 원본 캡처/비교/XML/Trace/DataEngine은 변경하지 않아요. 디코딩 실패·픽셀/메모리 상한·잘못된 base64는 명확히 실패해요.

최대 32MP, 한 변 32768px, 이미지당 20MB, 요청 64개 참조/64MB 원본·전송 합계를 각각 검사해요. 같은 이미지 참조는 대화 위치를 유지하면서 하나의 첨부를 공유해요. `off`는 중복 첨부도 유지하므로 전후 비교 기준으로 쓸 수 있어요. 서로 다른 과거 이미지는 임의로 제거하지 않아요. 기존 Transcript의 summary/recall/scrub 결과를 그대로 직렬화하며, 정리가 끝나지 않은 증거를 버리지 않아요. Explorer의 기존 crop/재관찰 결정과 한계는 그대로예요. 전송 변형 캐시는 메모리에서 최대 16MB/128개로 제한해요.

각 실행의 `*-usage.json`에는 에이전트/primary·fallback 단계별 실제 CLI usage, 이미지 치수·바이트·참조·첨부 수, 소요 시간을 기록해요. 대화 본문·화면·이미지 ID/내용 해시를 이 파일에 복제하지 않아요. 문맥이 제공되지 않는 native/독립 호출은 agent/stage를 unknown으로 표시해요. cached input을 input에 다시 더하지 않아요. usage 미반환/실패 호출이 있으면 전체 토큰 합계는 null(unknown)이고 알려진 부분합은 `known_*`로 구분해요. 가격이나 이미지 토큰을 추정하지 않아요.

로컬 Windows 실기기 수용은 [시나리오](../tests/fixtures/android-acceptance-scenarios.json)를 같은 시작 상태로 off/balanced 각각 10~20회 실행해서 비교해요. 가로·세로·접힘 상태와 팝업은 사용자가 먼저 준비하고, 실행 PC의 OS/기기/CLI 버전을 별도로 기록해요. 작은 글씨/팝업 여부는 기기별 실제 화면을 수동 검토해요.

```powershell
# 실제 모델 추론을 사용해요. 각 샘플은 별도 하위 폴더에 결과 하나만 저장해요.
callisto run "설정 앱의 배터리 화면을 확인해줘" --image-policy off --traces-path traces/off/battery/01
# 동일 시작 상태로 복원한 후
callisto run "설정 앱의 배터리 화면을 확인해줘" --image-policy balanced --traces-path traces/balanced/battery/01
python tools/compare_usage.py traces/off traces/balanced
```

비교기는 상대 시나리오/반복 폴더를 맞추고 실제 입력 토큰 감소율 중앙값·통과율·실패 호출·첨부 수·전체 실행 시간을 보여줘요. 누락/미확인 usage는 절감률로 만들지 않아요. 목표는 입력 토큰 중앙값 25% 이상 절감이며, 좌표/검증 정확도가 나빠지면 `off`로 돌아가고 실패 원인을 먼저 확인해요.

## Operator 문맥 정책 실험

기존 에이전트 설정의 `memory.transcript.context_policy`만 선택해요.
소스 기본값(`config/artemis.jsonc`)과 설치 패키지 기본값은 모두 `off`예요.
`shadow`는 기존 입력을 보내고 후보 바이트 이득·차단 사유를 계측해요.
`ready_only`는 검증된 연속 ready prefix의 송신 view와 이미지 pin 보호를 적용해요.
실기기 수용 전에는 `off`를 운영 기본값으로 유지하세요. 공급자·모델·추론 설정은 바꾸지 않아요.

- 현재 화면, 최근 raw 5 turns, 현재 loop의 tool/error/미실행 이력은 유지해요.
- pending/failed/unknown 요약, 남아 있는 픽셀 증거, pin, coverage 불일치,
  미완료 tool pair, 감소하지 않는 capsule은 조기 비용 교체를 막아요.
- 현재 ephemeral 안내가 있으면 상태를 추측하지 않고 전체 조기 압축을 보류해요.
- 조회/비교/unknown 이미지의 pin은 시간이나 연령으로 풀지 않아요.
  통합 호스트가 완료를 확인한 뒤 `ledger.release_evidence("decision:<observation_id>")` 같은
  정확한 이벤트를 전달해야 해요. 별도로 지정한 incident pin은 해당 해제 이벤트가 필요해요.
  공유 ledger commit에서 정상 dispatch·닫힌 tool pair·성공한 screenshot 조회와 후속 AI 판단을
  모두 확인하면 그 조회의 decision pin만 자동 해제해요. 비교·unknown·실패·incident는
  별도 소유권이므로 유지해요. incident의 실행 복구와 원래 목표 해결은 다르게 판단해요.
- pin은 최대 32개/원본 32 MB, registry는 4,096개예요. 초과하면 opt-in은 증거를 지우지 않고 오류를 내요.
  Shadow는 한도 문제를 기록하고 기존 경로를 유지해요. 기존 codec의 요청 상한도 계속 적용돼요.
- 정책을 `off`로 돌리면 새 비용 view를 해제해요. 이미 기존 scrub/hard 압축이 적용된
  문맥의 역복원은 보장하지 않으며 기존 DataEngine/checkpoint로 새 실행 문맥을 시작해야 해요.

새 usage의 `normalized_*` 합계와 `known_normalized_*` 부분합을 사용하세요.
기존 `input_tokens`/`cli_usage` 필드는 호환용 raw 의미를 유지하므로 공급자 간 직접 비교하지 마세요.
Claude 전체 입력은 세 입력 counter가 모두 있을 때만 계산해요. 단일 요청임을 확인하지 못한
CLI invocation 합계는 ledger의 context pressure 값으로 전달하지 않아요.
Gemini는 확인된 `models.*.tokens` 형태만 매핑하고 알 수 없는 형태는 raw로 보존해요.
캐시 읽기를 Codex 입력에 다시 더하지 않으며 누락 필드를 0으로 채우지 않아요.
계측 파일에 prompt 본문·이미지·내용 hash를 복제하지 않아요. run 내 digest 재노출은 횟수만 기록해요.

기기와 공식 CLI 추론 없이 비교하는 명령이에요. 실제 토큰은 항상 null로 남겨요.

```sh
CALLISTO_FORBID_LIVE_CLI=1 python tools/compare_operator_context.py --include-b --output dist/operator-context-comparison.json
# 가짜 Python 자식 실행도 생략하고 동일 codec/ledger만 비교
CALLISTO_FORBID_LIVE_CLI=1 python tools/compare_operator_context.py --include-b --no-child --output dist/operator-context-comparison.json
```

Windows에서는 먼저 `$env:CALLISTO_FORBID_LIVE_CLI="1"`을 설정한 뒤 같은 Python 명령을 사용해요.
실제 수용에서는 동일 시나리오와 시작 상태로 task/검증/복구 성공, 잘못된 PASS,
원본 재조회, 전체 에이전트의 입력·출력·캐시 usage와 지연을 함께 비교해야 해요.


### 2차 후보 선택·롤백 및 PC 수용

| 선택 | 기본값 | 동작 / 롤백 |
|---|---|---|
| `memory.transcript.context_policy` | `off` | 기존 `shadow` → 수용 후 `ready_only`; `off`로 비용 view 해제 |
| `CALLISTO_OPERATOR_IMAGE_POLICY` | `off` | `shadow`는 후보 계산만, `ready_only`는 보호 조건을 통과한 오래된 이미지 송신 사본만 ready summary로 대체; `off`로 해제 |
| `CALLISTO_COMPACT_TEXT` | 미설정 | `1`일 때 단일 순수 text block의 wrapper 축소; unset/`0`으로 원래 표현 |

이미지 view는 현재 화면, 최근 최소 5 turns, 현재 loop의 조회, 열린 tool transaction,
오류, 활성 안내, pin, unknown/comparison/recalled/overlay, pending/failed/unknown summary를
제거하지 않아요. 같은 바이너리의 서로 다른 evidence identity도 합치지 않아요.
이미지 리사이즈/crop 정책은 이 작업에서 변경하지 않아요. 기존 `--image-policy`와 별개예요.
송신 view는 되돌릴 수 있지만 기존 엔진의 scrub/hard fold 자체의 역복원은 보장하지 않아요.

Pin 소유권: 조회 decision은 한 관측의 tool 결과 소비에 한정해요. 정상 dispatch가 있어도
중간 오류, 호출 ID 불일치, 결과 미소비, 중단/timeout이면 유지해요. 실패 step의 incident pin은
`incident:<step_id>`이며 소유 호스트가 원래 의도 해결까지 확인한 명시적 이벤트로만 해제해요.
comparison/overlay/unknown은 자동 종료 신호가 없으므로 유지해요. 재시작 시 registry의
옛 decision 해제를 믿지 않고 재등록·재조회하고 미확정 pin은 다시 확인해요. 원본은 DataEngine에 남아요.
32 pinned evidence/32 MB/4096 registry 한도를 넘으면 shadow는 후보를 보류하고,
기존 ready_only 보호 경로는 명시적 오류를 내요. 조용한 evict나 timeout 해제는 없어요.

오프라인 매트릭스와 전체 회귀:

```sh
CALLISTO_FORBID_LIVE_CLI=1 python tools/compare_operator_context.py --include-b --include-v2 --no-child --output dist/operator-v2-comparison.json
CALLISTO_FORBID_LIVE_CLI=1 python -m pytest
```

PC에서 [환경 기록](../tests/fixtures/operator-cost-v2/baseline-metadata.json),
[수용 시나리오](../tests/fixtures/operator-cost-v2/scenarios.json),
[수동 판정 양식](../tests/fixtures/operator-cost-v2/acceptance.json)을 복사해 채워요.
CLI 버전, 동일 모델 설정을 뜻하는 비식별 label, 기기 화면 구성, 시작 상태와 시나리오 revision을 고정해요.
실제 raw usage/normalized scope를 설치된 공급자 1종에서 확인하고 불명확하면 null을 유지해요.
Codex input은 cached를 포함하고 uncached=input-cached, Claude는 fresh/read/write가 각각 있으며,
Gemini는 확인된 `models.*.tokens` 계약만 지원해요. 이 매핑의 실제 설치 버전 확인은 아직 필요해요.
요약·복구·재시도를 포함한 전체 agent 비용과 output/cache-write도 함께 비교해요.

유료 호출 전에 범위와 예상 호출 수 승인을 받은 뒤 같은 시작 상태로 off → shadow →
ready_only → 이미지 opt-in → text opt-in을 순차 비교해요(초기 권장 각 3회).
실행 PC에서만 `CALLISTO_FORBID_LIVE_CLI`를 해제해요. 각 scenario/repetition 폴더에
동일 session의 `*-result.json`, `*-usage.json`과 수동 `acceptance.json`을 두고, 각 모드 root에
`baseline-metadata.json`을 둬요. 실제 로그의 prompt/screenshot은 외부로 올리지 마세요.

```sh
python tools/compare_operator_acceptance.py traces/off traces/ready_only --output dist/acceptance-comparison.json
```

이 비교기는 공급자·CLI 버전·모델 설정 label·기기 구성·시나리오가 같고, 두 실행 모두 수동 성공과
필수 증거 보존을 확인한 경우에만 전체 uncached 절감률을 계산해요. provider 미상·scope 누계·
누락 usage는 제외하고 known 부분합은 별도 유지해요. 잘못된 PASS, 증거 누락, 위험한 Pin 해제,
복구 실패가 한 건이라도 있으면 opt-in을 끄고 원인을 재현해요. 15% uncached 절감은 검토 목표이며
자동 승인 기준이 아니에요. 출력·요약·재시도·행동 품질을 포함한 총비용 수용 뒤에만 기본값 변경을 검토해요.
