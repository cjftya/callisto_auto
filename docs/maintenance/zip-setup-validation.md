# ZIP 설치 및 글로벌 Skill 등록 점검

기준: 2026-10-20, 시작 SHA `5c0e463d95281bc54b4f0b9a5f3b601cc7269905`.

## 변경과 유지

- README에 GitHub ZIP 다운로드, 자유로운 고정 설치 경로, 스크립트 위치 기준 `.venv`, 세 CLI의 글로벌 Skill 경로와 두 등록 파일을 명시함.
- ZIP 삭제는 가능하지만 압축 해제한 설치 폴더는 유지해야 함. 설치 후 이동·이름 변경은 지원하지 않으며 새 위치의 기존 `.venv` 제거 후 Setup 재실행이 필요함을 명시함.
- 기존 구현이 요구사항을 충족하여 Setup·Skill 설치 실행 코드는 변경하지 않음. `setup.ps1`의 `$PSScriptRoot`, `setup.sh`의 스크립트 디렉터리 계산, `tools/bootstrap.py`의 `Path(__file__).resolve()`와 자식 프로세스 `cwd=ROOT`를 유지함.
- bootstrap의 기존 환경·소스 fingerprint 재사용, 공식 CLI 자동 탐색, 관리 중인 Skill의 절대 Python 경로 갱신, 사용자 수정 Skill 보호를 유지함.
- ARTEMIS Pro, 인증·모델 전송, ADB·Helper 설치 로직, PATH, 전역 Python 패키지, canonical Skill·라이선스·보존 manifest는 변경하지 않음.

## 검사 범위

- `tests/callisto/test_zip_setup.py`: 실제 PowerShell/POSIX shell launcher를 공백·한글 경로에 복사하고 다른 CWD에서 호출하여 bootstrap 경로·옵션 전달 확인. bootstrap은 부작용 없는 fixture이며 이 검사는 전체 설치·기기 수용 검사가 아님.
- 기존 bootstrap 회귀 확장: 임의 경로의 `.venv` 생성 대상, 자식 Python 절대 경로와 CWD, 다른 CWD에 환경을 만들지 않는지, 재실행 시 재사용 확인. Python/pip 자식과 venv builder는 mock임.
- 세 CLI별 임시 사용자 홈에서 실제 파일 등록·재등록: 두 파일만 존재, canonical Skill 바이트 일치, 재설치 시 Python 절대 경로 갱신, 수정된 Skill·메타데이터와 사용자 설정 fixture 보존 확인. 실제 사용자 인증 파일은 읽거나 변경하지 않음.
- 기존 다중 호스트 setup/check/repair 회귀와 전체 오프라인 회귀로 ADB·Helper·Pro 계약 검사. mock 성공을 실제 Android·모델 성공으로 간주하지 않음.

## 검증 결과

로컬 환경: Windows / Python 3.13.15. 모든 자동 검사는 `CALLISTO_FORBID_LIVE_CLI=1`로 수행함.

- 관련 회귀: **14 passed / 1 skipped**. POSIX shell이 기본 PATH에 없어 skip된 launcher 검사는 Git POSIX shell을 검사 프로세스 PATH에 추가한 별도 실행에서 **5 passed**로 확인함. 시스템 PATH는 변경하지 않음.
- 전체 `python -m pytest -q`: **2285 passed / 5 skipped / 8 deselected**. 위 POSIX shell skip 1개와 기존 skip 4개를 포함함. 정상 Windows 호스트의 PID/process 검사는 실행함.
- `ruff check callisto tools tests/callisto`: 통과. 도구는 프로젝트 `.venv`에만 추가함.
- `python -m pip check`: 통과.
- `python -m pip wheel --no-deps --no-build-isolation -w dist .`: 통과.
- `python tools/verify_wheel.py dist/callisto_auto-0.1.2-py3-none-any.whl --require-helper --report dist/zip-setup-wheel-report.json`: 통과. 새 venv 설치·pip check·CLI help·Pro/config import·세 호스트 Skill install/update/status 확인. Helper APK/manifest 검증과 APK 포함 wheel의 `bundle_valid=true` 확인. APK SHA-256은 `73590b206d576abd24beb0d35aee2657b6bd65af1e060db188e0a5de3365d6ec`로 기존 번들과 일치함.

해당 커밋의 Windows/Linux 회귀·wheel·Helper 빌드 결과는 [Offline validation](https://github.com/cjftya/callisto_auto/actions/workflows/offline.yml)에서 실행 SHA별로 확인함.

실제 AI CLI 로그인·추론, Android 연결·Helper 기기 설치·접근성 권한·Pro E2E는 수행하지 않음. 실제 사용자 글로벌 Skill을 덮어쓰는 설치도 수행하지 않음. Linux 호스트 실행은 Git POSIX shell 검사와 구분하여 CI로 확인함.
