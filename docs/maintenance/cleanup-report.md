# Callisto 전체 정리 결과

작업일: 2026-10-20 KST. 기준 `main`: `e2b2b36fd79c002a3758ad7e7eb672b688ae31c4`.
작업 브랜치: `chore/repository-cleanup`.

## 결과와 범위

기준선의 추적 파일 **641개**를 조사함. 사용 근거가 확인되지 않은 공개 코드의 삭제는 진행하지 않음. 실행·설정·Helper·스킬 관련 **351개 파일이 기준선과 바이트 단위로 동일**하며, Pro 보존 manifest **32 + 23개가 모두 일치**함. 배포 wheel의 **329개 항목도 정리 전후 경로·내용이 모두 동일**함.

이번 변경은 과거 문서의 아카이브 분리, 활성 문서 정합성, 잘못된 검증 전제 수정, 미사용 테스트 import 및 주석 정리임. 제품 런타임 코드·의존성·설정값·패키지 목록·진입점·CLI 실행 계약은 변경하지 않음.

파일별 역할·기준 SHA-256·참조 예·wheel 포함 여부·삭제/보존 판단은 [전체 조사 목록](cleanup-inventory.json)에 기록됨. 이 JSON은 기준선 641개 파일의 조사 증거이며 현재 아키텍처를 설명하는 지침 문서가 아님. 새 문서의 역할은 [아키텍처](../architecture.md)에 명시됨.

## 조사 방법과 한계

- `git ls-tree`의 전체 추적 파일과 각 파일의 원본 바이트 확보함.
- Python AST로 import/from-import 및 패키지 경로를 조사하고 동적 import·joinpath·glob·리소스 읽기 호출을 별도로 수집함.
- 설정의 workspace/bundled 경로, 공개 entry point, `_legacy_imports.py`, `artemis.__getattr__`, setuptools package-dir/data-files, CI, 설치 스크립트, fixture를 함께 검토함.
- 파일 경로·basename의 문자 참조는 후보 근거로만 사용함. 문서·테스트 참조도 포함되므로 실제 런타임 도달성의 증명으로 간주하지 않음.
- 정적 참조가 없더라도 공개 API·리소스·외부 사용자 가능성을 배제할 수 없는 파일은 보존함. 프로그램 전체의 동적 도달성이나 외부 사용자 사용량을 완전히 증명한 결과는 아님.
- Ruff F401의 runtime 후보 66개와 provider의 `shutil` 1개를 검토함. 재노출·원본 보존·patch/import 호환 가능성이 있어 유지함. 테스트에만 있는 미사용 import 5개를 제거함.

| 분류 | 파일 수 | 처리 |
| --- | ---: | --- |
| 정적 import/문자·리소스 참조 있음 | 213 | 유지 |
| 원본 보존 manifest | 55 | 원본 바이트 유지 |
| 패키지 initializer/export 경계 | 39 | 유지 |
| 공개 `python -m` 진입점 | 1 | 유지 |
| 명시적 SDK/alias/APK 호환 경계 | 15 | 유지 |
| 직접 사용을 입증하지 못한 공개 소스 | 5 | 삭제하지 않음 |
| 활성 회귀·fixture·명시적 integration/manual 테스트 | 218 | 유지 |
| 제거 기능의 과거 원본 테스트 | 40 | 이력 보존 |
| 현재 위치에서 아카이브로 이동한 과거 문서 | 5 | 원문 보존 |
| 설정·빌드·문서·메타데이터 등 | 50 | 역할 검토 후 유지 |

## 삭제·통합·문서 변경

### 제거한 미사용 내용

- `tests/callisto/test_boundaries.py`: 미사용 `asyncio` import 제거함.
- `test_v42_bootstrap.py`, `test_v42_images.py`, `test_v42_setup.py`: 미사용 `Path` import 제거함.
- `test_v4_contracts.py`: 미사용 `AIMessage` import 제거함.
- `pyproject.toml`: 폐기된 uv 빌드 backend 주석, 존재하지 않는 원격 SDK 의존성 주석, apps 경로 주석 정리함. TOML 파싱 결과는 기준선과 완전히 같음.

제품 Python 모듈·공개 함수·설정 항목·APK·테스트 케이스 자체를 삭제한 항목은 없음. 패키지 축소나 호환성 변경을 정리 실적으로 만들지 않음.

### 과거 문서 이동과 현재 문서 정리

다음 경로는 활성 `docs/`에서 제거하고 같은 파일명을 `docs/archive/`에 보관함.

- `plan-v3.0.md`
- `plan-v4.0.md`
- `cli-v4-audit.md`
- `cli-v4.1-report.md`
- `cli-v4.2-report.md`

각 문서의 원문·검증 수치·기준 SHA를 유지하고 현재 지침이 아니라는 안내를 추가함. 누적된 기존 `migration-status.md` 원문은 `archive/migration-status-v4-v4.2.md`로 보존하고 현재 상태 문서로 다시 작성함. 원격 SDK README 원문은 `archive/upstream-client-readme.md`로 보존함.

- `docs/architecture.md`: 현재 실행 구조·문서 역할·호환성 경계의 단일 기준으로 추가함.
- `README.md`: 빠른 시작·Helper 안내는 보존하고 현재 구조 및 아카이브 링크 정리함.
- `AGENTS.md`: 활성 문서 우선순위, 공개 SDK 보존 이유, 정리 시 동작 변경 금지 명시함. canonical APK 부재와 과거 root APK 존재를 구분함.
- `skills/callisto/SKILL.md` 및 `.agents` 포인터: 현재 host routing 계약과 일치하므로 바이트 변경 없음.
- `cli-capability-matrix.md`: 구버전 상태·검증 이력을 제거하고 세 CLI의 현재 구현과 실제 수용 미검증을 구분함.
- `advanced-setup.md`: 잘못된 `docs/docs/...` 상대 링크와 과거 버전 보고서 의존을 정리함.
- SDK README/DESIGN: 원격 사용법이 현재 Callisto 가이드로 읽히지 않도록 호환·과거 설계 경계 표시함.
- `tests/upstream_removed/README.md`: 과거 테스트의 목적, 수집 제외 및 실패 회피용 이동 금지 명시함. 40개 원본 파일 및 `archived-tests.json`은 변경 없음.

과거 문서의 모델 고정·Gemini 미구현·master 통합·Work 실행 지침은 현재 규칙으로 적용하지 않음. 기록을 삭제해 과거 검증 한계를 숨기지 않음.

## 유지한 레거시와 근거

| 대상 | 조사 결과 및 유지 이유 |
| --- | --- |
| 두 `artemis_client/` 트리 | 6개 파일이 모두 동일함. 루트는 checkout import, `packages/.../src`는 wheel 및 독립 SDK 빌드의 소스임. `artemis.interfaces.sdk`와 지연 공개 export가 사용함. 공개 호환성 때문에 둘 다 유지함. wheel에는 `artemis_client` 한 벌만 포함됨 |
| 원격 SDK HTTP transport·DTO·테스트 | 기존 공개 API임. Callisto는 원격 Daemon을 제공하지 않지만 SDK 제거는 별도 호환성 중단이므로 보존함 |
| `artemis/mcp/` | Pro 내부 in-process action session·FastMCP·ADB 계약에 사용됨. 두 외부 모듈 launcher의 실행 차단도 그대로 유지됨 |
| Flash 폴더 및 Explorer flash | 공유 summarizer/context compressor는 Pro에서 사용됨. `flash_runner.md`는 prompt assembly/action manifest 회귀가 읽음. 러너 소스는 기준선부터 없음 |
| `artemis/_legacy_imports.py`, 공개 facade·경로·진단 ID | 기존 import 객체 동일성, mock patch 및 저장 결과 호환성 때문에 유지함 |
| workspace/bundled JSONC | 전자는 ConfigEngine의 작업 공간 설정 계층이고 후자는 독립 wheel 기본값임. 바이트 일치 회귀가 있으나 단순 중복 파일이 아님 |
| `helper/ArtemisAccessibilityHelper.apk` | canonical bundle 경로가 아니고 SHA가 manifest와 다름. 런타임이 자동 사용하지 않으며 wheel에도 없음. 외부 사용 가능성 및 APK 보존 제약으로 삭제하지 않음 |
| Helper 소스·manifest·debug.keystore·build_apk.sh | 빌드·서명·기존 명령 호환 자산임. 빌드 정책·manifest 해시·서비스 ID 변경 없음 |
| `scripts/setup.ps1` | 루트 bootstrap 이전 개발용 설치 경로임. 외부 호출 여부를 증명할 수 없어 유지함. 기본 사용자 안내는 루트 setup 스크립트 사용 |
| `retry`와 `retry2` | `adbutils.screenrecord`가 `from retry import retry`로 간접 사용함. 두 배포가 같은 `retry/` 모듈 경로를 제공함. 한 배포의 uninstall로 다른 배포가 사용하는 파일도 사라지는 것을 확인했으므로 직접 의존성 삭제를 채택하지 않음. 공유 namespace·동작 동등성은 별도 호환성 검토 대상임 |
| `mcp`, `google-genai`, `httpx` 및 나머지 의존성 | 내부 FastMCP, Google 데이터형, 기존 perception/OCR 계약 등 사용 근거가 있음. 요구 패키지·제약·선택 의존성 변경 없음 |
| 영상 native/Files/agentic/audio 모듈 | 현재 CLI가 모든 기능을 지원하지 않아도 원본 엔진 및 보존 manifest·회귀 대상임. 미지원 경로를 가짜 구현으로 바꾸거나 삭제하지 않음 |

### 미사용을 입증하지 못해 보존한 소스

직접 incoming import/문자 참조가 발견되지 않은 다음 5개 파일은 공개 함수·클래스가 있어 보존함. 외부 호출 목록·폐기 정책이 확보되면 향후 별도 정리 가능함.

| 파일 | 외부 공개 표면·불확실성 |
| --- | --- |
| `artemis/drivers/android/hierarchy.py` | `parse_ui_hierarchy` 공개 parser |
| `artemis/drivers/android/input_ime.py` | `AndroidInputIME` 공개 입력 helper |
| `artemis/drivers/android/recorder.py` | `ScreenRecorder` 공개 녹화 helper |
| `artemis/drivers/cloud/cloud_driver.py` | `CloudDeviceDriver` 공개 driver. 현재 CLI의 지원 경로로 안내하지 않음 |
| `artemis/telemetry/replay.py` | `TraceReplayer` 공개 trace helper |

별도 검토 후보: `CloudDeviceDriver`에는 RPC 없이 성공값을 반환하는 기존 stub 메서드가 있음. 이번 조사에서는 현재 CLI의 호출 경로를 발견하지 못함. 제거·오류 처리 변경은 공개 동작 변경이므로 수행하지 않음. 이 클래스를 실제 cloud 지원 근거로 사용하면 안 됨.

## 기준선 실패와 검증 수정

기준 CI: [e2b2b36 / run 39364794837](https://github.com/cjftya/callisto_auto/actions/runs/39364794837).

1. Windows CLI 회귀: **1 failed / 354 passed / 1 skipped**. README는 `AI CLI용 스킬`로 설명하나 테스트가 `CLI 스킬` 고정 문자열을 검사했음. 실제 README 문구에 맞춰 테스트 기대값만 수정함. Pro 보존·Android 앱 라벨 검사도 그대로 유지함.
2. Linux 기준 전체 회귀: 로컬에서 **1 failed / 2229 passed / 29 skipped / 8 deselected**로 동일 README 실패 재현함.
3. 양쪽 Helper CI는 SDK 빌드·번들 상태·APK 포함 wheel 빌드까지 통과했으나 `verify_wheel.py`가 AI CLI 없는 clean venv에서 `skill install --directory`의 자동 탐색을 요구해 실패함. 로컬 기준 wheel 검증에서도 동일 실패 재현함.
4. wheel 검증은 `--ai-cli codex/claude/gemini`를 각 독립 임시 스킬 경로에 명시해 install/update/status를 모두 검사하도록 수정함. config import 검사에는 오프라인 provider scope와 임시 설정 경로만 지정함. 자동 탐색 자체는 기존 mock 회귀에서 유지됨. 모델·추론 수준이나 제품의 자동 탐색 기본값을 변경하지 않음.

## 검증 결과

로컬 환경: Linux x86_64 / Python 3.12.14. 실제 AI CLI·로그인·Android 호출 없이 `CALLISTO_FORBID_LIVE_CLI=1` 사용함.

| 검사 | 정리 전 | 정리 후 |
| --- | --- | --- |
| 전체 `python -m pytest` | 1 failed / 2229 passed / 29 skipped / 8 deselected | **2230 passed / 29 skipped / 8 deselected** |
| Pro manifest | 32 + 23개 일치 | **32 + 23개 일치**, 해시 변경 없음 |
| 실행·설정·Helper·스킬 파일 | 기준 351개 | **351개 바이트 동일** |
| frontend-free wheel | 생성 성공 | 생성 성공 |
| wheel 내부 파일 | 329개 | **329개 경로·내용 동일**, 추가·제거 없음 |
| wheel clean venv | 스킬 자동 탐색 실패 | 설치·pip check·Pro/config import·도움말·3개 호스트 스킬 install/update/status 통과 |
| `python -m pip check` | 통과 | 통과 |
| CI 범위 Ruff (`callisto tools tests/callisto`) | 기존 미사용 import는 ignore 정책 대상 | 통과 |
| `pyproject.toml` 파싱 결과 | 기준 | **전체 설정 동일** |
| 문서 상대 파일 링크·`git diff --check` | 잘못된 고급 가이드 링크 있음 | 통과 |

`retry` 간접 사용 조사 후 원래 의존성을 복구한 환경에서도 **2230 passed / 29 skipped / 8 deselected**로 재확인함. 29개 skip 및 8개 deselect 수는 유지됨. Work PID/procfs 불일치 17개와 Windows 전용 프로세스 테스트 등 기존 환경 조건을 변경하지 않음. 상세 skip 사유는 JUnit 증거에 보존됨. 테스트를 삭제·비활성화해 통과시킨 항목은 없음.

로컬 증거 요약은 [검증 JSON](cleanup-validation.json), wheel 검증 상세는 [wheel 보고서](wheel-report-linux.json) 참조. 실행 시점 JUnit은 CI artifact 및 작업 로그에 보관됨.

### Windows/Linux CI와 반영

정리 브랜치 PR의 Windows/Linux 회귀·일반 wheel·Helper 포함 wheel을 검증한 뒤 main으로 병합했으며, main에서도 같은 네 작업이 모두 통과함.

PR: [#1](https://github.com/cjftya/callisto_auto/pull/1). 정리 브랜치 검증 SHA: `b8936fc3ea61d25f696a053ceea7832ea694e024`.
PR CI: [run 39390309801](https://github.com/cjftya/callisto_auto/actions/runs/39390309801), **4개 작업 모두 통과**.

| CI 작업 | PR 결과 | main 결과 |
| --- | --- | --- |
| Linux 전체 Pro 회귀·일반 wheel | **2247 passed / 12 skipped / 8 deselected**, Ruff·pip check·격리 wheel 통과 | 통과 |
| Windows CLI·MCP·Helper 회귀·일반 wheel | **355 passed / 1 skipped**, PowerShell parser·Ruff·pip check·격리 wheel 통과 | 통과 |
| Linux Helper 빌드·APK 포함 wheel | APK 생성·번들 검증·wheel 생성·격리 설치 통과 | 통과 |
| Windows Helper 빌드·APK 포함 wheel | APK 생성·번들 검증·wheel 생성·격리 설치 통과 | 통과 |

main 병합 SHA: `14a9c5c7ab2698e00a93f4046684035ee3a914ca`.
main CI: [run 39390842657](https://github.com/cjftya/callisto_auto/actions/runs/39390842657), **완료·성공**. Linux 2247 passed / 12 skipped / 8 deselected, Windows 355 passed / 1 skipped로 재확인됨.

논리적 커밋: `29e8fe5` 테스트/격리 wheel 계약 수정, `b8936fc` 문서·조사·주석 정리, 이후 CI 증거만 문서 커밋으로 기록함. 마지막 결과 기록은 `docs/maintenance/`의 JSON·보고서만 변경하며 `[skip ci]`로 동일 코드의 재실행을 생략함. 검증된 실행·패키징 기준 SHA는 위 main 병합 SHA임. 최종 문서 커밋 SHA는 Git 이력에서 확인 가능함.

### 실행하지 않은 검증

- 실제 Codex/Claude/Gemini 로그인·모델 추론·이미지 인지·구독 usage 비교
- 실제 Android/ADB·Helper 설치·접근성 권한·UIAutomator2 fallback·복구·E2E
- Windows 로컬 설치 UI와 사용자 홈의 실제 호스트 스킬 인식
- 원격 SDK 서버와의 live 통신

오프라인·패키징 검증을 위 항목의 성공으로 표시하지 않음. 이번 작업에서 제품의 기능·알고리즘을 바꾼 항목은 없음.
