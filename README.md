# Callisto

Google ARTEMIS의 **기존 Pro 그래프·에이전트는 유지**하고, 모델 통신을 인증된 로컬 AI CLI로 연결하는 Android 자동 테스트 도구예요.

v4.1에서 **인증 환경변수 격리, 검증 결과와 종료 코드 일치, 스킬 설치와 Helper 배포**를 개선했어요. 실제 CLI 모델 호환성과 Android E2E는 공식 CLI와 기기가 연결된 실행 환경에서 확인해야 해요.

## 로컬 PC 설치

Python 3.12 이상, Android Platform Tools(ADB), 인증된 Codex CLI가 필요해요.

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
python tools/verify_local_cli.py --allow-live-cli
adb devices
callisto run "설정 앱에서 배터리 화면을 열고 배터리 항목이 표시되는지 확인" --device-serial SERIAL
callisto trace list
```

실행은 웹 UI·HTTP Daemon·외부 MCP 서버 없이 로컬 Pro 그래프로 진행돼요.
동일 호스트 AI의 현재 대화 세션을 재사용하는 방식은 아니며, 매 호출마다 기존 에이전트의 메시지 이력을 별도 CLI 프로세스로 전달해요.

`callisto run`은 세션 ID와 결과 JSON 경로를 출력해요. 원본 Trace, 체크포인트와 `run_outcome.json`을 함께 확인하세요.
종료 코드: **0 검증 통과 / 1 작업·검증 실패 / 2 검증 누락·미확정 / 130 취소**예요. `test_status=not_reported`도 2로 종료하고, 출력과 결과 JSON에 같은 `exit_code`를 기록해요. 잘못된 검증 요약도 성공으로 처리하지 않아요.

## 모델과 기능 범위

- Codex: 초기 구현 대상. 텍스트·이미지·JSON·도구 호출 반환·여러 턴 메시지 전달을 모의 테스트로 검증했어요. 기본 모델은 `gpt-6.1-sol`이에요.
- Claude Code: 텍스트 전송 실험 구현. `CALLISTO_AI_CLI=claude`와 `CALLISTO_MODEL`을 함께 지정해야 해요. 이미지 전송은 미구현이에요.
- Gemini CLI: 아직 미구현이에요. Google 원본의 native Files/Interactions/명시적 캐시·음성·검색 기능은 동등성이 확인되지 않았고, 호출 시 명시적으로 거부해요.
- 기존 Universal 영상 분석의 프레임/이미지 경로는 유지했어요. 실제 영상·음성 기능 전체가 동등하다고 주장하지 않아요.
- 선택적 OCR은 `CALLISTO_OCR=1`로 켜면 CLI 이미지 추론을 사용해 원래 텍스트/좌표 형식을 반환해요. 기존 Vision API 키로 자동 활성화하지 않아요. 실제 좌표 정확도 검증은 별도로 필요해요.

모델은 `CALLISTO_MODEL`, 실행 파일은 `CALLISTO_CODEX_EXECUTABLE`로 지정할 수 있어요. Codex 호출은 사용자 설정을 읽지 않고 저장된 공식 인증을 사용하며, 임시 디렉터리·read-only sandbox·JSON 출력으로 동작해요. 관리자가 강제한 정책은 우회하지 않아요.
자식 프로세스에는 주요 공급자의 API Key 및 해당 공급자의 대체 API 엔드포인트/라우팅 환경변수를 전달하지 않아요. 부모 환경과 공식 로그인 저장소는 변경하지 않아요. `HOME`/`USERPROFILE`/`CODEX_HOME`/`CLAUDE_CONFIG_DIR` 및 공식 CLI OAuth 환경은 정상 상속해요. Callisto는 인증 파일이나 토큰을 추출하지 않아요. CLI에 저장된 로그인 종류 자체는 검사하지 않으므로, 사용자 PC에서 공식 계정 로그인을 준비해야 해요.

Windows에서 `.cmd`/`.bat`로 발견되는 npm launcher는 명시적으로 거부해요. `CALLISTO_CODEX_EXECUTABLE`을 공식 native `.exe` 경로로 지정하세요. 오래된 CLI가 필수 옵션을 거부하면 업데이트 안내와 함께 실패하며, 안전 옵션을 빼고 재시도하지 않아요. 실제 버전별 호환성은 미검증이에요.

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

wheel은 프런트엔드 없이 설치되고, 정식 스킬 원본을 함께 배포해요. 설치한 Python 환경에서 아래 명령을 실행하면 Codex의 표준 사용자 경로 `~/.agents/skills/callisto`로 복사되어 프로젝트 밖에서도 발견할 수 있어요. pip 설치는 사용자 홈을 자동 변경하지 않아요.

```sh
callisto skill install
callisto skill status
# 패키지 업데이트 후
callisto skill update
```

`--directory <스킬 상위 폴더>`로 별도 경로도 지정할 수 있어요. 패키지 버전·내용 해시·설치 상태를 기록하고, 사용자가 수정한 파일이나 기존의 관리되지 않는 스킬은 덮어쓰지 않아요. 실행 중인 Codex에 나타나지 않으면 재시작하세요. 이 명령의 검증 범위는 경로와 파일이며, 실제 Codex의 인식 여부는 사용자 PC에서 확인해야 해요.

## Helper 빌드와 배포

소스 checkout과 기본 wheel에는 APK가 없어요. 기존 호환 Helper가 있으면 버전/프로토콜을 확인해 연결하고, 없으면 `auto` 계층 모드에서 UIAutomator2로 fallback해요. 실제 기기 호환성은 미검증이에요.

Linux/Windows 모두 JDK 17과 Android SDK Platform 35/Build Tools 35.0.0을 준비하면 셸 스크립트 없이 빌드할 수 있어요.

```sh
python tools/build_helper.py --sdk <Android-SDK-경로>
callisto helper bundle-status
# 빌드한 APK와 해당 manifest를 함께 포함하는 wheel
python -m pip wheel --no-deps --no-build-isolation -w dist .
```

`helper-build` CI는 두 OS에서 개발용 APK/manifest와 APK 포함 wheel을 빌드해 Actions artifact로 제공해요. 이는 기존 debug 서명을 사용하는 개발 빌드이며 production release는 아니에요. 빌드·서명·독립 wheel 설치의 성공 여부는 [v4.1 결과](docs/cli-v4.1-report.md)에 구분해서 기록해요.

별도 APK를 사용할 때는 **APK와 일치하는 `helper_manifest.json`을 같은 폴더에** 두고 `CALLISTO_HELPER_DIR`로 지정하세요. `callisto helper bundle-status`는 기기 접근 없이 경로/버전/SHA-256을 검사해요. 패키지·버전·해시가 맞지 않는 번들은 설치하지 않아요. `callisto helper status --serial SERIAL --json`은 사용자 PC에서 설치 버전과 응답 프로토콜을 확인해요. 이미 설치된 앱을 강제로 다운그레이드하지 않아요.

- [v4.1 기능 보존·개선·검증 보고서](docs/cli-v4.1-report.md)
- [v4 감사 및 변경 근거](docs/cli-v4-audit.md)
- [CLI 지원 현황](docs/cli-capability-matrix.md)
- [전환 진행 상황](docs/migration-status.md)
- [원본 보존 기준](docs/upstream-baseline.md)
- [CLI Skill](skills/callisto/SKILL.md)
- [라이선스](LICENSE), [제3자 고지](third_party/mobile_use/NOTICE)
