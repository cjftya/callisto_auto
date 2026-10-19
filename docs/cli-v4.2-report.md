# Callisto v4.2 구현·검증 보고서

작성일: 2026-10-20 KST · 패키지: callisto-auto 0.1.2

## 기준과 실행 환경

- 기준 main: `27458eb10faa4b328dffda45972b8a87fa07c340`.
- 구현 SHA: 이 문서를 포함한 v4.2 커밋에서 확인할 수 있어요. 이후 최종 반영 SHA는 커밋 이력으로 확인해요.
- 검증 환경: ChatGPT Work, Linux x86_64, Python 3.12.14.
- 제품 기본 추론 설정: 공식 Codex CLI / `gpt-6.1-sol` / reasoning `medium` / Pro / 이미지 `balanced`.
- 실제 AI CLI 버전: 미조회. 공식 CLI·모델 추론·로그인 검사는 이 환경에서 실행하지 않았어요.
- Android 기기 및 Windows 호스트: 미연결/미실시.

## 구현 결과

1. AI 첨부에만 이미지 정책을 적용해요. 긴 변 balanced 1920/quality 2560/economy 1440, JPEG 80/90/75이며 off는 원본 기준선이에요. 실제 포맷을 검사해서 MIME을 교정하고, 알파·색 모드·EXIF 저장 픽셀 프레임·메모리/입력 상한을 처리해요. 잘못된 이미지는 누락 없이 실패해요.
2. 원본 캡처/XML/Trace/DataEngine·이미지 비교를 유지해요. Pro 정규화 좌표는 동일하고, 픽셀을 반환하는 선택적 OCR은 역변환과 범위 검사를 거쳐요.
3. 동일 이미지의 첨부만 공유하고 메시지/도구 ID/이미지 참조 순서는 유지해요. 기존 Transcript의 요약·scrub·recall은 그대로 전달해요. 서로 다른 과거 증거를 임의로 삭제하는 새 로직은 없어요. 16MB/128개 메모리 캐시를 사용해요.
4. `setup.ps1`, `setup.sh`, `callisto setup/check/repair`를 제공해요. Python 환경·패키지·pip check·CLI 도움말·native 경로·공식 로그인 상태·ADB·기기 선택·관리 스킬·검증 Helper를 연결해요. 사용자 설정은 한 파일로 저장하고 실행 옵션 > 환경변수 > 사용자 설정 > 기본값 우선순위를 적용해요. 기존 노드별 모델 설정은 명시 override가 없을 때 유지해요.
5. setup은 모델 추론이나 테스트 탐색을 실행하지 않아요. Windows Python 자동 설치는 사전 동의를 받고, Codex/ADB가 없으면 조치를 안내해요. 다중 기기는 명시 선택하며 비대화형에서는 추측하지 않아요. 관리되지 않는 스킬·사용자 수정은 보존해요.
6. 실제 usage와 에이전트/단계별 호출 수·이미지 수/치수/용량·시간을 집계해요. 미확인 토큰은 null이고 알려진 부분합은 구분해요. cached input은 input에 다시 합산하지 않아요. compare_usage.py는 같은 상대 샘플 폴더의 결과끼리 비교해요.
7. README를 3단계로 줄이고 고급 가이드·12개 수용 시나리오·준비 상태 확인 스킬을 추가했어요. CI push 기준은 main이에요.

## 검증 증거

| 검사 | 결과 |
|---|---|
| 변경 전 CLI 기준선 | 87 passed / 2 skipped |
| 전체 오프라인 회귀 | **2202 passed / 29 skipped / 8 deselected**, 90.14초 |
| 마지막 Skill·설정 회귀 | 37 passed, 2.00초 |
| 원본 핵심 보존 manifest | **32 + 23개 모두 일치**; 해시 갱신 없음 |
| ruff | 통과 (`callisto tools tests/callisto`, 수정한 adapter 주변 모듈 포함) |
| pip check | No broken requirements found |
| frontend-free wheel | callisto_auto-0.1.2-py3-none-any.whl 빌드 통과 |
| 독립 가상환경 wheel 설치 | pip check, Pro/config/adapter imports, 모든 CLI 도움말, Skill install/update/status 통과 |
| Linux 셸 구문 | `sh -n setup.sh` 통과 |
| Windows PowerShell/프로세스 | CI에 AST 구문 검사 및 Windows 회귀 구성; 이 Linux 호스트에서 미실시 |
| Helper SDK 빌드·서명/설치 | 이 호스트에서 미실시; 기존 Linux/Windows helper-build CI 유지, 새 manifest에 protocol_version 추가 |
| 실제 모델/Android 전후 비교 | **미실시**; 절감률·통과율·좌표 정확도는 미검증 |

29개 skip에는 이 Work 실행기의 PID/procfs namespace 불일치로 정상 호스트에서 실행해야 하는 기존 테스트, OS/선택 기능 테스트 등이 포함돼요. 8개는 설정상 제외된 외부 환경 테스트예요. 기존 경고 89개는 모의 객체/의존성 관련이며 통과로 바꿔 기록하지 않았어요.

원본 로그는 작업 checkout의 `dist/tests.xml`, `dist/wheel-report.json`과 작업 디렉터리의 `v42-full-final.log`, `v42-wheel-check-final.log`, `v42-skill-final.log`, `v42-wheel-build-final.log`에 있어요. 커밋 후 CI의 동일 SHA Actions artifact에서도 tests.xml/wheel-report.json을 확인할 수 있어요. 이 보고서는 CI가 끝나기 전에 CI 성공을 주장하지 않아요.

## 토큰·정확도 비교

| 항목 | off 기준선 | balanced | 판단 |
|---|---|---|---|
| 실제 모델 input/cached/output tokens | unknown | unknown | 실제 CLI 사용 없음 |
| 실제 시나리오 첨부 수·실행 시간 | 미측정 | 미측정 | 측정 경로와 비교기 구현 |
| 실기기 검증 통과율·좌표 정확도 | 미측정 | 미측정 | 수용 시나리오 준비 |
| 입력 토큰 중앙값 25% 절감 | 미확인 | 미확인 | 목표이며 달성으로 표시하지 않음 |

Windows 실행 PC에서 같은 초기 상태로 10~20개 샘플을 off/balanced 각각 실행하고 `python tools/compare_usage.py traces/off traces/balanced`로 비교해요. 예시와 수동 화면 회전/폴더블/팝업 준비 방법은 advanced-setup.md에 있어요. 정확도가 악화되면 off로 되돌려요. 이미지 바이트 감소를 모델 토큰 절감으로 간주하지 않아요.

## Helper 배포 주의점

현재 canonical bundle에는 APK가 없어서 기본 source/wheel은 fallback을 명시해요. `helper/ArtemisAccessibilityHelper.apk`의 SHA-256은 `a98c5f484da4dac4d3b615a9865ff819be2459ebd614a622ae5852a97e3cb9ba`이고 canonical manifest의 값 `133e373fe03615c251cd74b03a38539c844d09a074954bca2d2dde6684561969`와 달라요. 이 APK를 검증된 번들로 간주하거나 해시만 다시 써서 설치하지 않았어요.

setup은 일치하는 APK/manifest와 지원 protocol_version이 있는 빌드만 설치해요. 기존 호환 Helper가 있으면 protocol/활성 상태를 확인하고, 없으면 UIAutomator2 fallback을 표시해요. CI에서 함께 빌드한 APK·manifest 포함 wheel은 사용자 PC에 SDK/JDK 없이 설치할 수 있어요. 실제 기기 동작 검증은 별도예요.

## Git 상태와 남은 항목

- main 기준 구현 및 CI 트리거 정리를 완료했어요.
- master는 기준 main보다 1커밋 뒤이며 고유 커밋 0개, 열린 base:master PR 0개로 재확인했어요.
- `git push origin --delete master`는 GitHub Git 인증 부재(`could not read Username`)로 실패했어요. GitHub 커넥터에는 브랜치 삭제 도구가 없고 브라우저도 미로그인 상태여서 삭제 완료로 표시하지 않아요.
- 코드의 GitHub 반영 결과는 최종 커밋 이력과 최종 작업 응답에서 확인해요. 원격 main이 바뀌면 덮어쓰지 않고 예상 SHA 검사를 적용해요.
- **v4.2 코드 구현/오프라인 검증 완료와 Windows·실기기·절감 목표의 수용 완료를 구분해요.**
