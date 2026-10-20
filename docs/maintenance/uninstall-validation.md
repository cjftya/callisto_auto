# 소스 설치 제거 검증

2026-10-20 Windows 로컬 작업. 대상은 ZIP/checkout 소스 설치이며 Pro 엔진·기존 setup·인증·보존 manifest는 변경하지 않음. 실제 사용자 설치를 제거하지 않고 pytest의 공백·한글 경로 임시 설치본만 삭제함. 모든 검증에 `CALLISTO_FORBID_LIVE_CLI=1` 적용함.

## 구현과 삭제 경계

- `uninstall.ps1` / 실행 가능한 `uninstall.sh`가 자기 위치의 `tools/uninstall.py`를 호출함. CWD나 고정 Documents 경로로 설치 위치를 추정하지 않음.
- 소스 마커·패키지명·절대 경로·루트/홈/사용자 컨테이너/시스템 경로·조상 링크를 검사함. 내부 링크/정션은 Python 3.12+ `shutil.rmtree`가 연결 대상까지 순회하지 않고 제거함. Linux `.venv/bin/python`의 정상 심볼릭 링크는 등록의 논리 경로로 비교함.
- 글로벌 Skill은 두 파일만 있고, package/관리 SHA-256/현재 `.venv` Python 경로가 일치할 때만 제거함. 손상·수정·추가 파일·다른 설치·링크는 보존하고 이유를 표시함.
- 설정은 설치별 소유권 정보가 없으므로 기본 보존함. 사용자 확인 후 `-RemoveSettings` / `--remove-settings`를 미리보기와 실행에 함께 사용해야 함. 다른/비관리 Skill이 있거나 디렉터리에 추가 파일·알 수 없는 설정 내용이 있으면 보존함. `CALLISTO_CONFIG`는 자동 제거하지 않음. 등록되지 않은 설치까지 검색하지 않음.
- 최종 승인은 전체 설치 경로 입력 또는 승인 후 정확한 `-ConfirmRoot` / `--confirm-root` 전달임. 비대화형 입력만으로는 제거하지 않음. 승인 후와 외부 작업자에서 범위·루트 파일 ID를 다시 비교함.
- 프로세스 목록은 Windows CIM / Linux procfs로 검사함. 충돌은 PID만 보고하고 프로세스를 강제 종료하지 않음. Windows 가상환경 Python 중계 실행 파일과 PowerShell 런처는 자기 실행의 조상임을 확인해 구분함.
- 외부 임시 디렉터리에 복사한 작업자가 외부 base Python으로 실행됨. 런처 종료를 최대 60초 기다린 뒤 삭제함. `SCHEDULED`는 성공이 아니며 `result.json`이 완료/실패/보존 항목을 기록함. 작업 스크립트·job은 정리하고 결과·로그는 사용자가 확인하도록 남김. 실패 시 README 수동 절차로 남은 경로를 확인함.
- 기기 Helper 앱, 시스템 Python/ADB, AI CLI/로그인, 외부 파일·Trace는 삭제 대상이 아님. Windows에서 기존 PowerShell 창이 남아 있으면 종료 대기 실패가 될 수 있음을 README에 명시함.

## 로컬 검증

- Windows Python 3.13.15. 제거 회귀 **19 passed / 1 skipped**: 관리 Skill·기본 설정 opt-in 제거, 다른 설치·사용자 수정·손상된 메타데이터·개인 파일/인증 파일 보존, 위험 경로, 승인 거절/잘못된 승인, 권한 실패 보고, 변경된 승인 범위 거부, 충돌 PID 거부, 정션 대상 보존, 실제 외부 작업자 및 시스템/venv/PowerShell 런처 자기 삭제 확인함. Linux 셸 항목은 Windows에서 skip됨.
- Windows PowerShell 5.1과 PowerShell **7.6.7**에서 별도 미리보기 런처 검사 **2 passed**. 다른 CWD에서 공백·한글 경로 호출 검증함.
- `python -m ruff check callisto tools tests/callisto` 통과함.
- `python -m pip check` 통과함. `setuptools wheel` 준비 후 `python -m pip wheel --no-deps --no-build-isolation -w dist .` 통과함.
- `python tools/verify_wheel.py dist/callisto_auto-0.1.2-py3-none-any.whl --report dist/uninstall-wheel-report.json --require-helper`: 격리 설치·의존성·Pro/import·CLI help·세 호스트 Skill install/update/status·canonical Skill·Helper APK/manifest 확인 통과함. 실제 CLI/Android를 실행하지 않음.
- 첫 전체 회귀는 **1 failed / 2300 passed / 7 skipped / 8 deselected**. 변경하지 않은 `test_data_engine_handler_queue_buffering_and_background_worker`에서 0.4초 안에 50개 중 24개 로그만 반영되어 실패함. 해당 테스트 단독 재실행은 **1 passed**임. 이 시간 의존 실패를 숨기기 위해 엔진이나 테스트 대기값을 변경하지 않음.
- 프로세스 수정 후 최종 `python -m pytest -q --junitxml=dist/uninstall-final-tests.xml`은 **2300 passed / 10 skipped / 8 deselected**로 통과함. POSIX 전용 3개, Android 진단 4개, Gemini live SDK 2개, DataEngine fixture 1개가 skip됨. 추가한 PowerShell 7 매개변수 검사는 별도 2개 런처 검사에 포함됨. `git diff --check`와 staged diff 검사 통과함.

## 한계

Linux 직접 실행은 이 Windows 호스트에서 수행하지 않음. 기존 Windows/Linux Actions 회귀에 제거 테스트를 포함하고 Windows 스크립트 구문 검사도 확장함. CI 결과가 나오기 전 Linux 통과로 간주하지 않음. 실모델·Android·기기 Helper 제거/재설치와 AI 호스트의 Skill 인식은 이번 범위에서 실행하지 않음. 동시 프로세스/파일 변경이 시작되는 모든 경쟁 상황이나 OS 파일 잠금의 부재를 보장하지 않으며, 삭제 실패는 결과 경로를 보고 수동 정리함.
