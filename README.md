# Callisto

Callisto는 Google ARTEMIS의 **기존 Pro 자동화 엔진을 유지**하면서 AI CLI용 스킬로 전환한 Android 자연어 테스트 도구임. Codex·Claude Code·Gemini CLI에서 자연어로 요청하면 스킬이 `callisto run`을 호출하고, 기존 Pro 엔진이 계획·탐색·조작·검증·복구를 수행함.

모델 추론은 로그인된 공식 로컬 AI CLI를 이용함. API Key 기반 직접 모델 호출, 웹 UI, 외부 MCP 서버는 필요하지 않음. 내부 `artemis/` 모듈과 Helper의 Android 패키지 ID·APK 파일명은 호환성을 위해 유지함. 사용자에게 표시되는 이름은 **Callisto**를 사용함.

## 빠른 시작 — 3단계

### 1. 설치 스크립트 실행

1. [GitHub 저장소](https://github.com/cjftya/callisto_auto)의 **Code → Download ZIP**으로 다운로드함.
2. 사용자가 원하는 고정 경로에 압축을 해제함. 예: Windows `D:\Tools\Callisto`, Linux `~/tools/Callisto`. 특정 디렉터리는 필요하지 않음.
3. 압축을 해제한 프로젝트 폴더에서 운영체제에 맞게 아래 Setup을 실행함.

Windows PowerShell:

```powershell
.\setup.ps1
```

Linux:

```sh
./setup.sh
```

공식 설치 진입점은 루트 `setup.ps1` / `setup.sh`임. `scripts/setup.ps1`은 경고 후 루트 설치기로 위임하며, 과거 `-Python` 옵션은 거부함.

- Python 3.12 이상 확인 후 **Setup 스크립트가 있는 프로젝트 루트**에 `.venv`를 생성하고 Python 의존성과 Callisto를 설치함. 다른 작업 디렉터리에서 스크립트의 전체 경로로 호출해도 설치 위치는 같음. AI CLI·ADB·Helper 상태도 점검함.
- Windows에서 Python 설치가 필요하면 사용자 동의를 요청함. Linux에서 Python이 없으면 별도 설치 필요.
- 사용할 AI CLI(Codex·Claude Code·Gemini CLI 중 하나)는 공식 설치 및 로그인이 필요함. Callisto는 CLI 인증이나 시스템 PATH를 임의로 변경하지 않음.
- 설치된 Codex·Claude Code·Gemini CLI를 자동 탐색하고, 사용 가능한 모든 CLI에 Callisto 스킬을 각각 등록함. 설치 시 CLI를 선택할 필요 없음. 특정 CLI만 점검·복구할 때만 `--ai-cli` 옵션 사용.
- 중단 이후 재실행 시 준비된 환경을 재사용함. 미해결 조건은 `ACTION_REQUIRED`와 후속 조치로 표시됨.

### 설치 폴더와 글로벌 Skill

Callisto 엔진과 Python 라이브러리는 압축을 해제한 원본 폴더와 그 안의 `.venv`에 유지됨. 글로벌 Skill에는 다음 두 파일만 등록하며 ZIP·엔진 복사본이나 심볼릭 링크를 만들지 않음.

| AI CLI | 글로벌 Skill 폴더 |
| --- | --- |
| Codex | `~/.agents/skills/callisto/` |
| Claude Code | `~/.claude/skills/callisto/` |
| Gemini CLI | `~/.gemini/skills/callisto/` |
| Antigravity CLI (`agy`, host registration only) | `~/.gemini/antigravity-cli/skills/callisto/` |

Antigravity CLI가 설치되어 있으면 Setup이 해당 호스트의 Skill도 등록함.
`callisto setup check --json --ai-cli antigravity`로 점검하며,
`callisto skill install --ai-cli antigravity`의 `install`을 `update`·`status`로 바꿔 갱신·확인 가능함.
**Pro 추론은 현재 `UNSUPPORTED`**: 비도구 이미지 입력과 전체 도구 차단이 검증되지 않음.
`run --ai-cli antigravity`는 종료 코드 2로 중단하고 다른 CLI로 전환하지 않음.
제거 스크립트는 이 설치에 연결된 관리 Skill만 삭제하며 사용자 수정·비관리 Skill은 보존함.
IDE/앱의 `~/.gemini/config/skills/`는 설치·제거 대상이 아님.
탐색에는 PATH, `CALLISTO_ANTIGRAVITY_EXECUTABLE` 또는 공식 기본 경로인
Windows `%LOCALAPPDATA%/agy/bin/agy.exe`, Linux `~/.local/bin/agy`를 사용함.
설치·로그인은 공식 CLI에서 수행함. [CLI 지원 범위](docs/cli-capability-matrix.md) 참조.

- `SKILL.md`: canonical `skills/callisto/SKILL.md`에서 등록한 실행 지침.
- `callisto-install.json`: 해당 `.venv` Python의 절대 경로(`python_executable`), 패키지 버전 및 Skill 관리 해시. Skill은 이 Python으로 실행할 수 있으므로 가상환경 활성화나 시스템 PATH 변경이 필요하지 않음.

> Callisto는 Setup 스크립트가 있는 프로젝트의 실제 위치를 설치 기준 경로로 사용함. **설치 후 원본 폴더 이동·이름 변경은 지원하지 않음.** 글로벌 Skill의 절대 실행 경로와 가상환경이 유효하지 않을 수 있음.

설치 위치를 변경하려면 새 위치의 프로젝트에서 기존 `.venv`를 제거하고 Setup을 다시 실행함. 새 `.venv`를 생성하고 관리 중인 글로벌 Skill의 Python 실행 경로를 갱신함. 기존 사용자 설정과 AI CLI 인증 정보는 삭제하지 않음. 사용자 수정 Skill은 자동 덮어쓰지 않으며 `ACTION_REQUIRED` 안내에 따라 직접 백업·이동한 뒤 재실행해야 함.

설치 완료 후 다운로드한 ZIP은 삭제해도 됨. **압축을 해제한 설치 폴더는 계속 유지해야 함.**

### 2. Android 연결 및 권한 승인

Android 기기를 USB로 연결하고 **개발자 옵션 → USB 디버깅**을 활성화한 뒤, 기기에 표시되는 USB 디버깅 승인 창을 허용함.

- 연결 기기가 한 대라면 자동 선택됨. 여러 대라면 Windows `.\setup.ps1 -DeviceSerial SERIAL` 또는 Linux `./setup.sh --device-serial SERIAL`로 지정함.
- `ACTION_REQUIRED`가 표시되면 안내된 항목을 해결하고 설치 스크립트를 다시 실행함.
- Helper 설치 또는 접근성 서비스 활성화가 차단된 경우 아래 [Helper APK 설치 및 권한 문제 해결](#helper-apk-설치-및-권한-문제-해결) 참조.

### 3. AI CLI에서 자연어로 테스트 요청

설치한 AI CLI를 다시 실행한 뒤 다음과 같이 요청함.

> 칼리스토로 설정 앱의 배터리 화면이 정상적으로 열리는지 테스트해줘.

스킬이 실행 명령을 전달하고 기존 Pro 엔진이 Android 테스트 및 검증을 수행함. 사용자가 직접 모델이나 추론 수준을 Callisto에 설정할 필요 없음. 다만 호스트 AI 대화에서 일시적으로 선택한 모델은 별도 자식 CLI 프로세스에 자동 상속되지 않으며, 자식 CLI는 자체 공식 사용자 기본 설정을 사용함.

## 설치 제거(완전 삭제)

실행 중인 Callisto 테스트·Setup을 먼저 종료하고 필요한 파일을 백업함. **스크립트가 있는 설치 폴더 전체를 영구 삭제함.** `.venv`, 내부 Trace 및 사용자가 추가한 개인 파일도 함께 삭제됨. 다른 작업 폴더에서 전체 경로로 호출해도 동일한 설치를 대상으로 함.

Windows PowerShell(실제 설치 폴더에서):

```powershell
.\uninstall.ps1 -DryRun
.\uninstall.ps1
```

Linux(실제 설치 폴더에서):

```sh
./uninstall.sh --dry-run
./uninstall.sh
```

미리보기로 삭제·보존 경로 확인 → 설치 폴더의 전체 경로를 입력하여 최종 승인 → 외부 작업자에서 제거 → 출력된 `result.json` 확인 순서임. `SCHEDULED`는 접수 상태이며 완료가 아님. Windows에서는 호출 PowerShell 프로세스가 종료되어야 삭제를 시작함. 기존 PowerShell 창에서 실행했다면 경로를 복사한 뒤 해당 창을 닫아야 함(60초 대기 후에도 열려 있으면 삭제하지 않고 실패 기록함). 결과의 `status`, `removed`, `failed`, `preserved`를 확인함. 임시 작업 스크립트는 자체 정리하며 결과·로그 폴더는 확인 후 직접 정리 가능함.

등록 메타데이터가 현재 설치의 `.venv`를 가리키고 관리 해시가 일치하는 글로벌 Skill만 제거함. 다른 설치·수정된 Skill·추가 파일이 있는 Skill은 보존함. 시스템 Python, 타 프로젝트 가상환경, Android SDK/ADB·연결 기기·설치된 Helper 앱, AI CLI와 로그인·인증 정보, 외부 사용자 파일·Trace 및 다른 Callisto 설치는 유지됨.

Callisto 사용자 설정은 여러 설치가 공유할 수 있어 **기본 보존함**. 다른 설치가 사용하지 않음을 확인한 경우에만 Windows `-RemoveSettings` 또는 Linux `--remove-settings`를 미리보기와 실행에 동일하게 추가함. 다른 설치/비관리 Skill이 발견되거나 설정 디렉터리에 추가 파일이 있으면 계속 보존함. `CALLISTO_CONFIG`로 지정한 커스텀 설정은 자동 삭제하지 않음. 스크립트는 등록되지 않은 다른 설치까지 탐색하지 않으므로 설정 공유 여부는 사용자가 확인해야 함.

AI CLI에서는 “칼리스토 완전히 삭제해줘”라고 요청 가능함. Skill이 실제 설치 경로를 검증하고 미리보기와 백업 안내를 제시한 뒤 최종 승인을 받아 공식 스크립트를 실행함. 승인된 비대화형 호출에 한해 Windows `-ConfirmRoot '<미리보기의 전체 설치 경로>'` 또는 Linux `--confirm-root '<미리보기의 전체 설치 경로>'` 사용 가능함. 일반 비대화형 호출은 삭제를 거부함. 설치 폴더 이동·이름 변경은 계속 지원하지 않으며 새 위치에서 Setup 재실행 필요함.

### 스크립트를 실행할 수 없는 경우 수동 제거

1. Callisto 작업·Setup 및 해당 설치를 사용하는 Codex·Claude·Gemini·Antigravity CLI 세션을 종료함.
2. `~/.agents/skills/callisto/`, `~/.claude/skills/callisto/`, `~/.gemini/skills/callisto/`, `~/.gemini/antigravity-cli/skills/callisto/`의 `callisto-install.json`을 확인함. `python_executable`이 **삭제하려는 설치의 `.venv`**를 가리키고 관리 파일이 수정되지 않았음을 확인한 뒤 해당 Skill 폴더만 삭제함. 다른 설치의 Skill, 사용자 수정 Skill, 인증 정보와 IDE 전용 Antigravity Skill은 보존함. 손상된 메타데이터만으로 연결을 추정하지 않음. 기기의 Helper 앱은 제거 대상이 아님.
3. 사용자가 압축 해제한 실제 Callisto 설치 폴더를 확인하여 폴더 전체를 삭제함. `.venv`와 내부 Trace도 제거됨. 홈·드라이브 루트·다른 프로젝트 경로를 지정하지 않음.
4. 다른 설치에서 사용하지 않는 경우에만 전용 설정을 정리함. Windows 기본 위치는 `%LOCALAPPDATA%\callisto\settings.json`, Linux는 `${XDG_CONFIG_HOME:-~/.config}/callisto/settings.json`임. 전용 디렉터리도 내부 파일을 확인한 뒤 정리함. `CALLISTO_CONFIG`가 설정되어 있으면 그 위치와 공유 여부를 별도로 확인함.
5. 외부 Trace·사용자 파일은 직접 확인 후 정리함. 일부 삭제 실패 시 결과에 기록된 나머지 경로와 잠금/권한 원인을 확인한 뒤 수동 정리함. 이미 원본 파일이 일부 사라진 설치는 검증 실패할 수 있으므로 제거 스크립트 재실행 성공을 가정하지 않음.

## Helper APK 설치 및 권한 문제 해결

**Callisto Accessibility Helper**는 Android 화면의 접근성 계층을 읽는 보조 앱임. 신뢰할 수 있는 Callisto 빌드에만 접근성 권한을 허용해야 함. 권한 설정은 기기 보안 정책과 사용자 승인이 필요할 수 있음.

**현재 소스와 이 소스에서 빌드한 wheel에는 검증된 Helper APK·manifest가 포함됨.** 일반 사용자는 Helper를 직접 빌드할 JDK·Android SDK 빌드 도구 없이 setup으로 설치할 수 있으며, 기기 연결용 ADB는 필요함. APK가 제외된 배포에서 기존 호환 Helper도 없다면 UIAutomator2 fallback을 사용함. 실제 기기 설치·fallback 호환성은 별도 검증 필요.

### 1. 설치 상태 확인 및 복구

아래 점검·복구 명령은 설치된 모든 AI CLI의 스킬을 대상으로 함. 특정 CLI만 확인하려면 `--ai-cli codex`(또는 `claude`, `gemini`) 지정.

```sh
callisto setup check --json
callisto helper bundle-status
callisto helper status --json
```

- `bundle-status`: 로컬 APK·`helper_manifest.json` 존재 여부 및 SHA-256 일치 여부 확인. APK 미포함 배포에서는 실패 코드가 나올 수 있으며, 이 결과만으로 Callisto 전체 설치 실패를 의미하지 않음.
- `helper status`: Android 연결 상태에서 `installed`(설치), `enabled`(접근성 서비스), `reachable`(응답), `protocol_supported`(프로토콜) 확인.
- 검증된 번들이 있는 경우 `callisto setup repair`로 설치·복구 재시도 가능함.
- 특정 기기에 명시적 재설치가 필요할 때만 `callisto helper install --serial SERIAL --force` 사용. 해당 기기의 기존 앱 상태·서명을 우선 확인해야 함.

`callisto` 명령이 PATH에 없으면 Windows에서는 `.\.venv\Scripts\python.exe -m callisto.cli`, Linux에서는 `./.venv/bin/python -m callisto.cli`로 대체 가능함. 예: `.\.venv\Scripts\python.exe -m callisto.cli helper status --json`.

### 2. 설치 오류별 해결 방법

| 증상 | 확인 및 조치 |
| --- | --- |
| `adb devices`에 `unauthorized` 또는 `offline` 표시 | USB 케이블·디버깅 승인 상태 확인 후 재연결. 다중 기기는 시리얼 지정 필요. |
| `bundle_valid=false` 또는 APK/manifest 불일치 | **같은 빌드에서 생성한** `ArtemisAccessibilityHelper.apk`와 `helper_manifest.json` 필요. 서로 다른 빌드의 파일 혼용 금지. |
| APK 설치가 보안 정책으로 차단됨 | 기기에 표시된 설치 차단 사유 확인. Galaxy는 아래 **보안 위험 자동 차단** 항목 참조. 회사 관리 기기는 관리자 정책 준수 필요. |
| APK 설치 후 접근성 서비스를 켤 수 없음 | 아래 **Android 13 이상 제한된 설정** 절차 확인. |
| `enabled=false` | Android 접근성 설정에서 Helper를 직접 활성화한 뒤 상태 재확인. |
| `enabled=true`이나 `reachable=false` | USB 연결과 실행 중인 다른 UIAutomator2/Appium 세션 충돌 확인. 다른 테스트 세션 종료 후 재점검. |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | 이전 설치 앱과 새 APK의 서명 불일치 가능성 확인. 임의 삭제·재설치 전에 기존 설정과 설치 이력 확인. |
| 다운그레이드 또는 프로토콜 불일치 | 기존 앱 버전 및 번들 버전 확인. 최신 앱을 무조건 다운그레이드하지 않으며 호환되는 검증 번들 사용 필요. |

### 3. Android 13 이상: 제한된 설정으로 접근성 권한이 막힌 경우

외부에서 설치한 앱은 Android 버전·설치 경로에 따라 접근성 서비스가 **제한된 설정**으로 차단될 수 있음. APK 출처를 신뢰할 수 있는 경우에만 아래 절차 진행.

1. **설정 → 애플리케이션(앱) → Callisto Accessibility Helper** 이동. 이전 APK에서는 `Artemis Accessibility Helper`로 표시될 수 있음.
2. 앱 정보 화면의 **우측 상단 더보기(⋮) → 제한된 설정 허용** 선택. 제조사·OS 버전에 따라 메뉴 구성은 다를 수 있음.
3. **설정 → 접근성 → 설치된 앱(또는 다운로드한 앱) → Callisto Accessibility Helper**에서 서비스 활성화.
4. `callisto helper status --json`으로 `enabled`, `reachable`, `protocol_supported` 재확인.

참고: [Google Android 제한된 설정 공식 안내](https://support.google.com/android/answer/12623953?hl=ko). 접근성 권한은 화면 내용을 읽고 앱을 조작할 수 있는 민감한 권한이므로 출처가 불분명한 APK에 허용하면 안 됨.

### 4. Samsung Galaxy: 보안 위험 자동 차단으로 APK 설치가 막힌 경우

일부 Galaxy 기기의 **설정 → 보안 및 개인정보 보호 → 보안 위험 자동 차단** 기능이 외부 APK 설치 및 USB 명령을 차단할 수 있음.

1. 기기의 설치 차단 메시지와 차단 원인을 먼저 확인함.
2. 신뢰할 수 있는 개발용 APK를 본인이 승인한 테스트 기기에 설치하는 경우에만 보안 설정의 임시 조치를 검토함.
3. 설치 및 권한 승인 완료 후 임시로 변경한 보호 설정은 복원함. 회사 관리 기기는 관리자 정책을 우회하지 않음.

참고: [Samsung 보안 위험 자동 차단 공식 안내](https://r1.community.samsung.com/t5/손쉬운-해결-방법/보안-위험-자동-차단-기능으로-갤럭시-기기의-보안-강화-방법/ba-p/28156187). 모든 설치 실패를 해당 기능 탓으로 판단하거나 보안 기능 해제를 기본 절차로 요구하지 않음.

### 5. Helper APK가 없는 경우

- APK 미포함 소스·wheel에서는 UIAutomator2 fallback 경로 사용 가능. Helper가 필요한 경우 별도 검증된 APK 번들 확보 필요.
- [GitHub Actions — Offline validation](https://github.com/cjftya/callisto_auto/actions/workflows/offline.yml)의 `helper-build` 작업은 Windows·Linux용 개발 APK, 대응 manifest 및 APK 포함 wheel을 생성하도록 구성됨. 실제 빌드 성공과 산출물 제공 여부는 해당 실행 결과에서 확인 필요.
- 외부 번들은 **`ArtemisAccessibilityHelper.apk`와 `helper_manifest.json`을 같은 폴더에** 배치하고, `CALLISTO_HELPER_DIR`을 해당 폴더로 지정함. Android 패키지 ID `com.artemis.helper`와 APK 파일명은 기존 호환성을 위해 유지됨.
- 직접 빌드는 **JDK 17, Android SDK Platform 35, Build Tools 35.0.0** 준비 후 `python tools/build_helper.py --sdk <Android-SDK-경로>` 실행. 세부 절차는 [고급 설치·운영 가이드](docs/advanced-setup.md) 참조.
- 제공되는 APK는 기존 디버그 서명을 사용하는 **개발용 빌드**이며 프로덕션 서명 APK와 동일하지 않음.

## 점검 및 복구

```sh
callisto doctor --json
callisto setup check --json
callisto setup repair
callisto trace list
```

- `doctor`: 실행 파일·설정 중심 점검이며 AI 추론은 실행하지 않음.
- `setup check`: 설치된 모든 CLI의 스킬·환경·ADB·Helper 점검. Codex 로그인 상태는 별도 조회하지만 Claude·Gemini 인증은 실제 실행 시 확인 필요.
- `setup repair`: 발견된 모든 CLI의 관리 중인 스킬 복구 및 검증된 Helper 번들 준비. 한 스킬이 수정되어 있어도 다른 CLI의 등록을 계속하며, 사용자 수정 파일은 덮어쓰지 않음.
- `READY`: 실행 준비 상태. Setup의 다음 실행 안내에는 준비된 CLI 이름만 표시됨. **모델 추론 및 Android 테스트 성공을 의미하지 않음**. `ACTION_REQUIRED`: 안내된 조치가 필요한 상태.
- 종료 코드: **0 검증 통과 / 1 작업·검증 실패 / 2 검증 누락·미확정 / 130 취소**. 실제 성공 여부는 결과 JSON과 원본 Trace 기준으로 판단함.

## 구현 및 호환성

- **Pro 엔진 유지:** 계획·탐색·조작·검증·복구는 기존 ARTEMIS Pro 엔진에서 수행함. Flash 실행 프로필은 지원하지 않음.
- **모델 독립성:** 특정 모델이나 추론 수준을 강제하지 않으며 선택한 공식 CLI의 기본 설정을 사용함. Codex·Claude·Gemini 어댑터 구현됨.
- **이미지 정책:** 기본 `balanced`는 모델에 첨부하는 화면만 긴 변 1920px 이하로 변환함. 원본 캡처·Trace·UI XML 및 Pro 검증 흐름 유지. 실제 토큰 절감률과 정확도는 로컬 검증 필요.
- **검증 한계:** CLI 어댑터 모의 계약 테스트는 구현되었으나 실제 로그인·이미지 추론·Android E2E와 설치 버전별 호환성은 사용자 PC에서 검증 필요.
- **실행 환경:** Windows PowerShell·Linux 설치 스크립트 제공. API Key 기반 직접 모델 호출, 별도 웹 UI, 외부 MCP 서버는 사용하지 않음.

## 참고 문서

- [고급 설치·설정·제한사항](docs/advanced-setup.md)
- [현재 아키텍처와 문서 역할](docs/architecture.md)
- [지원 범위](docs/cli-capability-matrix.md)
- [원본 보존 기준](docs/upstream-baseline.md) · [라이선스](LICENSE)

이전 계획과 검증 보고서는 Git 이력에서 확인할 수 있으며, 현재 기준은 위 문서 및 코드임.
