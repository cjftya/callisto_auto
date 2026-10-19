# Callisto

Google ARTEMIS Pro 엔진으로 Android를 자연어 테스트해요. 추론은 로그인된 공식 로컬 AI CLI를 사용해요.

## 빠른 시작 — 3단계

1. 저장소를 받은 폴더에서 PowerShell로 실행해요.

   ```powershell
   .\setup.ps1
   ```

   Python 3.12+ 환경과 Callisto 설치, 기본 설정, Codex native 실행 파일 탐색, 로그인 상태, ADB·스킬·Helper 확인을 한 번에 진행해요. 필요한 Python 설치는 먼저 동의를 물어봐요. Codex CLI와 Android platform-tools가 없으면 설치할 항목을 안내해요. 시스템 PATH·CLI 인증 설정을 직접 바꾸지 않아요.

2. Android를 USB로 연결하고 **USB 디버깅 허용**을 승인해요. 첫 실행 결과가 `ACTION_REQUIRED`이면 안내를 처리한 뒤 같은 명령을 다시 실행해요. 여러 기기는 `.\setup.ps1 -DeviceSerial SERIAL`로 선택해요.

3. Codex CLI를 다시 열고 요청해요.

   > Callisto로 설정 앱의 배터리 화면이 정상적으로 열리는지 테스트해줘.

설치된 스킬이 가상환경의 Python 경로를 찾아 실행하므로 매번 가상환경을 활성화할 필요는 없어요. 실제 Codex의 스킬 인식은 실행 PC에서 확인해야 해요.

Linux는 `./setup.sh`를 사용해요. 재실행은 준비된 의존성을 재사용해요. Python 설치·공식 CLI 로그인·USB 승인이 필요한 상태를 성공으로 처리하지 않아요.

## 점검과 복구

설치 환경의 `callisto setup check`는 구성·공식 로그인 상태·기기·Helper를 점검해요. `callisto setup repair`는 관리 중인 설정과 스킬을 복구하고, 선택한 기기에 검증된 Helper만 설치해요. 가상환경을 활성화하지 않았다면 `.\setup.ps1 -Check` 또는 `.\.venv\Scripts\python.exe -m callisto.cli setup repair`를 사용해요.

`READY`는 실행 준비 상태예요. 실제 추론·Android 테스트 통과를 의미하지 않아요. setup은 유료 모델 추론을 실행하지 않아요. Helper가 없는 배포는 UIAutomator2 fallback을 표시하고, APK와 manifest가 일치하지 않으면 설치를 거부해요.

기본 모델은 `gpt-6.1-sol`, reasoning은 `medium`, 이미지는 `balanced`예요. 원본 캡처·Trace·UI XML·Pro의 판단/검증 흐름은 유지하고, AI 첨부만 긴 변 1920px 이하로 줄여요. 입력 토큰 절감률과 실제 기기 정확도는 로컬 비교로 확인해야 해요.

- [고급 설치·설정·제한사항](docs/advanced-setup.md)
- [v4.2 구현·검증 보고서](docs/cli-v4.2-report.md)
- [지원 범위](docs/cli-capability-matrix.md) · [전환 현황](docs/migration-status.md)
- [원본 보존 기준](docs/upstream-baseline.md) · [라이선스](LICENSE)
