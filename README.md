# Callisto

Callisto는 Google ARTEMIS의 기존 Pro 자동화 엔진을 유지하면서, **AI CLI(Codex 등)에서 호출하는 CLI 스킬**로 전환한 Android 자연어 테스트 도구예요. 스킬은 `callisto run`을 호출하는 인터페이스이고, 실제 계획·탐색·조작·검증은 보존한 Pro 엔진에서 수행해요. 모델 추론은 로그인된 로컬 AI CLI를 이용하며 API Key 기반 직접 모델 호출이나 웹 UI·외부 MCP 서버는 필요하지 않아요.

내부 `artemis/` 모듈과 Android Helper의 패키지 ID·APK 파일명은 기존 호환성을 위해 유지해요. 사용자에게 보이는 CLI 상태·도움말과 새로 빌드하는 Helper의 표시 이름은 **Callisto**를 사용해요.

## 빠른 시작 — 3단계

1. 저장소를 받은 폴더에서 PowerShell로 실행해요.

   ```powershell
   .\setup.ps1
   ```

   Python 3.12+ 환경과 Callisto 설치, 기본 설정, Codex native 실행 파일 탐색, 로그인 상태, ADB·스킬·Helper 확인을 한 번에 진행해요. 필요한 Python 설치는 먼저 동의를 물어봐요. 선택한 CLI의 필요한 도구와 Android platform-tools가 없으면 설치할 항목을 안내해요. 시스템 PATH·CLI 인증 설정을 직접 바꾸지 않아요.

2. Android를 USB로 연결하고 **USB 디버깅 허용**을 승인해요. 첫 실행 결과가 `ACTION_REQUIRED`이면 안내를 처리한 뒤 같은 명령을 다시 실행해요. 여러 기기는 `.\setup.ps1 -DeviceSerial SERIAL`로 선택해요.

3. AI CLI를 다시 열고 요청해요. 현재 Android 이미지 추론은 Codex CLI에서 구현됐으며, Claude Code와 Gemini CLI는 아래 지원 범위를 확인해야 해요.

   > Callisto로 설정 앱의 배터리 화면이 정상적으로 열리는지 테스트해줘.

설치된 스킬이 가상환경의 Python 경로를 찾아 실행하므로 매번 가상환경을 활성화할 필요는 없어요. 실제 Codex의 스킬 인식은 실행 PC에서 확인해야 해요.

Linux는 `./setup.sh`를 사용해요. 재실행은 준비된 의존성을 재사용해요. Python 설치·공식 CLI 로그인·USB 승인이 필요한 상태를 성공으로 처리하지 않아요.

Helper APK는 본체와 별도로 `python tools/build_helper.py --sdk <Android-SDK-경로>`로 빌드할 수 있어요(JDK 17, Android SDK Platform 35/Build Tools 35.0.0 필요). 생성된 APK는 `helper_manifest.json`과 함께 보관해야 하며, `CALLISTO_HELPER_DIR`로 해당 폴더를 지정할 수 있어요. 기존 `com.artemis.helper` 패키지를 유지하므로 새 APK는 동일 앱을 업데이트해요.

## 점검과 복구

설치 환경의 `callisto setup check`는 구성·공식 로그인 상태·기기·Helper를 점검해요. `callisto setup repair`는 관리 중인 설정과 스킬을 복구하고, 선택한 기기에 검증된 Helper만 설치해요. 가상환경을 활성화하지 않았다면 `.\setup.ps1 -Check` 또는 `.\.venv\Scripts\python.exe -m callisto.cli setup repair`를 사용해요.

`READY`는 실행 준비 상태예요. 실제 추론·Android 테스트 통과를 의미하지 않아요. setup은 유료 모델 추론을 실행하지 않아요. Helper가 없는 배포는 UIAutomator2 fallback을 표시하고, APK와 manifest가 일치하지 않으면 설치를 거부해요.

Callisto는 특정 모델이나 추론 수준을 지정하지 않고 선택된 AI CLI의 기본 동작을 사용해요. 이미지 정책은 `balanced`예요. 원본 캡처·Trace·UI XML·Pro의 판단/검증 흐름은 유지하고, AI 첨부만 긴 변 1920px 이하로 줄여요. 입력 토큰 절감률과 실제 기기 정확도는 로컬 비교로 확인해야 해요.

- [고급 설치·설정·제한사항](docs/advanced-setup.md)
- [v4.2 구현·검증 보고서](docs/cli-v4.2-report.md)
- [지원 범위](docs/cli-capability-matrix.md) · [전환 현황](docs/migration-status.md)
- [원본 보존 기준](docs/upstream-baseline.md) · [라이선스](LICENSE)
