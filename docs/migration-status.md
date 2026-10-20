# Callisto 전환 현황

Antigravity CLI (`agy`) supports host registration, explicit selection and managed Skill removal.
Global directory: `~/.gemini/antigravity-cli/skills/callisto/` (separate from IDE/app).
Pro inference with `--ai-cli antigravity` is UNSUPPORTED pending validated non-tool image
input, complete tool blocking, structured output/usage and Android E2E. No provider fallback.
Evidence: [Antigravity integration](maintenance/antigravity-integration.md).

기준: 2026-10-20, 정리 시작 `main` SHA `e2b2b36fd79c002a3758ad7e7eb672b688ae31c4`.

CLI 스킬 기반 전환이 구현되어 있음. 기존 ARTEMIS Pro 엔진이 계획·탐색·조작·검증·복구를 수행하고, Codex·Claude Code·Gemini CLI 어댑터가 별도 공식 CLI 프로세스로 추론을 전달함. 모델·추론 수준은 공식 CLI 사용자 기본값에 위임됨.

현재 구조는 [아키텍처](architecture.md), 구현된 기능과 한계는 [지원 범위](cli-capability-matrix.md), 설치·Helper 문제 해결은 [README](../README.md)와 [고급 가이드](advanced-setup.md)를 기준으로 함.

## ZIP 설치 및 글로벌 Skill 안내

기존 Setup·Skill 등록 구현을 유지하고 README에 ZIP 다운로드·임의 고정 경로·스크립트 위치 기준 `.venv`·세 CLI 글로벌 Skill의 역할을 명시함. 설치 폴더 이동·이름 변경은 지원하지 않으며 경로 변경 시 새 위치의 `.venv` 재생성과 Setup 재실행이 필요함. 재실행·경로 갱신·사용자 수정 보호 및 Windows/Linux 검증 근거와 실기기 미검증 범위는 [ZIP 설치 점검](maintenance/zip-setup-validation.md)에서 관리함.

## 소스 설치 완전 제거

루트 `uninstall.ps1` / `uninstall.sh`와 표준 라이브러리 공통 작업자를 추가함. 스크립트 위치의 소스 마커·보호 경로·링크·실행 프로세스·글로벌 Skill 등록을 검사하고, 미리보기 및 정확한 설치 경로의 명시적 승인 후 설치 폴더 전체를 삭제함. 기본 설정은 공유 가능성 때문에 보존하며 별도 opt-in 검사로만 제거함. README 자동/수동 안내와 canonical Skill의 최종 승인 절차를 반영함. Pro·setup·보존 manifest는 변경하지 않음. 최신 검증과 실제 호스트별 미검증 범위는 [제거 검증 기록](maintenance/uninstall-validation.md) 참조.

## Helper APK 기본 번들

사용자 요청에 따라 [c451c8f의 Windows Helper CI](https://github.com/cjftya/callisto_auto/actions/runs/39434029212)에서 생성한 APK와 대응 manifest를 `packages/artemis-accessibility-helper/`에 함께 포함함. 버전 1.2.1 / versionCode 7 / protocol 2, APK SHA-256은 `73590b206d576abd24beb0d35aee2657b6bd65af1e060db188e0a5de3365d6ec`임. 원본 엔진·과거 `helper/` APK·보존 manifest는 변경하지 않음.

환경변수 지정 없이 `callisto helper bundle-status`에서 `apk_present: true`, `bundle_valid: true`를 확인함. 로컬 Windows 전체 오프라인 회귀는 **2281 passed / 4 skipped / 8 deselected**이며 `pip check`·프런트엔드 없는 wheel 빌드·소스/wheel APK 해시 일치 검사도 통과함. 출처 CI의 APK 포함 wheel 격리 검증도 통과했으며 실제 기기 설치·접근성 서비스 활성화는 별도 사용자 검증 대상임.

## Windows ADB 설정 진단

`callisto/setup.py`의 `adb devices` 출력에 `encoding="utf-8", errors="replace"`를 적용함. 실행 파일 미발견에만 platform-tools 설치를 안내하고, 실행 실패·시간 초과·기기 미연결·unauthorized·offline은 원인별 조치를 안내함. 기존 ADB 경로·서버·Skill·인증·Helper fallback 흐름은 유지함.

Windows Python 3.13.15, 기본 CP949, UTF-8 모드 꺼짐 환경에서 관련 설정 회귀 64개 및 전체 오프라인 회귀 **2274 passed / 11 skipped / 8 deselected**가 통과함. 실제 자식 프로세스의 UTF-8·잘못된 바이트 출력 디코딩과 `setup`·`setup check`·`setup repair`의 원인별 안내를 검증함. 린트·`pip check`·프런트엔드 없는 wheel 빌드도 통과함. 실제 ADB·Android·모델 CLI 및 PowerShell 7 직접 실행은 수행하지 않음. Linux 로컬 실행 환경은 없으며, Linux 회귀는 해당 커밋의 기존 Actions 결과로 확인함.

## 전체 정리 상태

정리 범위·파일별 삭제/보존 판단·기준선 및 정리 후 검증은 [정리 결과 보고서](maintenance/cleanup-report.md)에서 관리함. 런타임 알고리즘·정책·기본값·공개 import·설치 경로·Helper·이미지/좌표·최종 판정은 변경하지 않음.

- 과거 v3/v4/v4.1/v4.2 계획·검증 기록은 [아카이브](archive/README.md)에 분리됨. 과거 Gemini 미구현·특정 모델 고정·master 통합 지침을 현재 설계로 적용하지 않음.
- 보존 manifest 32 + 23개 및 원본 라이선스를 유지함. 해시 기대값을 재생성하지 않음.
- 원격 SDK는 기존 공개 import와 소스 실행·wheel 호환성 때문에 유지함. 현재 Callisto HTTP Daemon 지원으로 해석하지 않음.
- 원본 제거 기능 테스트는 `tests/upstream_removed/`와 `archived-tests.json`에 보존됨. 현재 회귀의 실패를 숨기기 위해 이동·삭제하지 않음.
- main 및 PR의 Windows/Linux 오프라인 회귀·wheel 격리 설치·Helper 빌드는 [Actions](https://github.com/cjftya/callisto_auto/actions/workflows/offline.yml)에서 실행 SHA별로 확인함.

## 검증 구분

정리 전 기준선은 **1 failed / 2229 passed / 29 skipped / 8 deselected**임. 실패는 README 표현을 검사하는 고정 문자열 불일치임. 기준 CI의 양쪽 Helper 빌드·wheel 생성은 통과했으나 격리 wheel 검사가 AI CLI 자동 탐색에 의존해 실패했음. 정리 후 최종 수치·CI 링크는 위 정리 보고서에 기록함.

이번 작업은 ChatGPT Work의 Linux/Python 3.12 환경에서 오프라인으로 수행함. 실제 AI CLI·로그인 검사·모델 추론·Android 기기 테스트는 실행하지 않음. Windows 검증은 실제 Windows CI 결과와 로컬 Linux 검증을 구분함. 호스트 PID와 `/proc`가 다른 환경의 원본 프로세스 검사 skip은 기존 조건대로 유지됨.

과거 실기기 Helper 상태 진단이나 다른 SHA의 회귀 통과는 이번 정리의 E2E 통과 증거가 아님. 실제 설치 버전별 호환성·정확도·토큰 절감률은 사용자 실행 PC에서 확인해야 함.
