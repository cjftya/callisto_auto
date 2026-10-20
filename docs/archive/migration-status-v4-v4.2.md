> **과거 전환 기록 — 현재 상태로 해석하지 않음.** [현재 전환 현황](../migration-status.md) 참조. 당시 검증 수치와 한계는 원문 보존됨.

> **v4.1 최신 결과:** [기능 보존·호환성·검증 보고서](cli-v4.1-report.md). 아래 v4 기록은 당시 상태예요. v4.1은 Native Explorer opt-in, 인증 환경 격리, 검증 누락 exit 2, 스킬 설치 명령 및 선택적 Helper 포함 wheel을 추가해요. 실제 AI CLI·Android 검증은 여전히 미완료예요.

# Callisto v4 전환 상태 — 2026-10-19

**코드 정리 완료, 실제 CLI·Android 실사용 검증 미완료.**
호스팅 앱에 따른 실제 CLI 실행 금지 규칙은 제거했어요. 선택된 실행 환경에서
공식 CLI를 통해 승인된 Pro 테스트를 실행해요. 자동 회귀는 명시적 오프라인
스위치로 실제 추론을 차단하고 fake CLI·모킹·정적 검사·도움말/import를 검증해요.

## Helper 서비스 이름 수정 — 2026-10-19

전체형과 축약형 Android 서비스 이름을 정규화해 접근성 상태 오판을 수정했어요.
상태 확인뿐 아니라 활성화 시 중복 등록 방지와 재연결/삭제 시 서비스 제거에도 적용해요.
다른 패키지나 클래스는 일치하지 않으며 다른 접근성 서비스는 유지해요.
Windows / Python 3.13 전체 회귀는 **2158 passed, 7 skipped, 8 deselected**이고
`pip check` 및 원본 보존 해시 32개 + 엔진 해시 23개가 통과했어요.
수정 후 연결 기기의 Helper 상태는 활성화·응답·프로토콜 지원 모두 true로 확인됐어요.
정식 Skill과 사용자 영역의 관리 중인 Skill 모두 Work별 실행 금지 문구를 제거했어요.
프런트엔드 없는 wheel 빌드와 `tools/verify_wheel.py`의 clean venv 설치,
Pro/config import, CLI 도움말, Skill install/update/status 검증도 통과했어요.
로그: `traces/helper-fix-pytest.log`, `traces/helper-fix-wheel.log`;
wheel 보고서: `traces/helper-fix-wheel-report.json`. 기본 wheel에는 Helper APK가 없어요.
실제 AI CLI 및 배터리 화면 자동화 성공 여부는 여전히 미검증이에요.

## 변경 결과

- Pro 그래프, Planner/Operator/Checker/Validator/Diagnoser 및 프롬프트 등 보존 manifest **32개 파일의 SHA-256 일치**.
- API 키 유무에 따른 Explorer/영상 분석 경로 분기 제거. 기존 Universal 프레임 엔진을 사용하고, 명시적으로 주입한 native 호환 포트는 원본 알고리즘 검사에 사용해요.
- Settings의 API 키 수집·저장과 Vertex ADC 조회를 비활성화했어요. 과거 키 getter는 None, 저장·ADC는 명시적 미지원 오류예요.
- 남아 있던 ADB/XML 모듈의 외부 MCP `__main__` 진입점은 명시적 오류로 종료하게 차단했어요. 내부 도구 함수와 in-process 세션은 유지해요.
- 직접 AI 공급자를 모두 거부하고 Google SDK import는 `google.genai.types`로 제한하는 회귀를 추가했어요.
- OCR의 미사용 HTTP 클라이언트·Vision 파서를 제거했어요. opt-in CLI OCR의 text/polygon 형식과 실패 전파를 검사해요.
- 기본 모델·추론 수준 강제 지정은 제거하고, CLI 자체의 선택에 맡기도록 정리했어요. 기존 모델 라벨은 호환성 데이터로만 취급해요.
- 공급자 자체 shell/apps/plugins/hooks/subagent/search를 비활성화하는 명령을 구성하고, 응답에 공급자 도구 실행 이벤트가 있으면 실패로 처리해요.
- 웹 정적 산출물 7개와 브라우저 리소스 accessor를 삭제했어요. 불필요한 직접 의존성 10개를 제거했지만 google-genai types와 내부 MCP는 유지해요.
- 독립 설치에서 드러난 MCP 2.x 비호환을 막도록 `mcp<2`로 제한했어요. FastMCP v1 액션 계약은 바꾸지 않아요.
- Callisto 배포 메타데이터로 버전을 조회하고, 호환 client 패키지·표준 Skill·Helper manifest를 wheel에 포함해요.
- master/main push 및 PR에서 Linux 전체 회귀와 Windows CLI/프로세스 회귀, 양쪽 wheel 격리 설치를 실행하도록 CI를 구성했어요.
- `.gitattributes`의 LF 규칙으로 Windows checkout도 원본 파일 해시를 보존해요. 해시 기대값을 바꾸지 않았어요.

원본 API/웹/외부 MCP/Flash runner 테스트는 `tests/upstream_removed/`에서 이력을 유지해요.
적용 가능한 버전·설정·리소스 계약은 활성 Callisto 테스트로 옮겼어요.
내부 in-process MCP, Pro 공유 summarizer/compressor, Explorer `flash` tier는 보존했어요.
파일별 판정과 근거: [v4 감사 보고서](cli-v4-audit.md).

## 로컬 오프라인 증거

환경: Linux x86_64 / Python 3.12.14. 시작 master `c56d3c7`, main `3aa3ccb`.

- 시작 기준선: **2076 passed, 27 skipped, 8 deselected**, 87 warnings.
- v4 전체 회귀: **2100 passed, 29 skipped, 8 deselected**, 89 warnings.
- skip 29개 = 기존 27개 + Windows 전용 fake 자식 트리 테스트 2개.
  기존 skip에는 Work의 PID namespace와 host `/proc` 불일치로 제외한 테스트 17개가 있어요.
  이 17개는 일반 Linux CI에서 실행돼요. 실제 기기/API 관련 원본 검사는 기본 suite에 포함하지 않아요.
- `pip check`: 깨진 의존성 없음. 정적 lint와 `git diff --check` 통과.
- 보존 manifest: 32/32 일치. 활성 소스의 Google SDK Client/credential import 없음.
- wheel 빌드 및 별도 clean venv 설치 통과. checkout 밖에서 Pro graph·실제 CLI 실행 함수·호환 SDK client import, 기본 설정, 모든 CLI 도움말과 버전을 확인했어요. AI CLI 실행 없음.
- wheel에 표준 Skill, Helper 버전 manifest, 라이선스가 포함되고 웹/외부 서버/Flash runner 산출물은 없음을 확인했어요. APK 없음도 명시적으로 기록해요.
- 위 코드 검증의 GitHub 커밋: `2c489641b01c53cac3b1e11360ba450a1e331bea` (원본 보존 해시도 일치).
- GitHub Actions는 각 master/main HEAD에서 별도로 검증하며, 테스트 XML 및 wheel-report JSON을 artifact로 남겨요. [Actions 결과](https://github.com/cjftya/callisto_auto/actions/workflows/offline.yml)에서 실행 SHA와 결과를 확인할 수 있어요.

## 설치와 실사용 제한

- Codex는 필수 transport 구현 대상이며 fake 텍스트/이미지/schema/tool 왕복/여러 턴을 검증해요. 실제 계정 인증과 모델 호환성은 미검증이에요.
- Claude 텍스트는 실험 단계, 이미지 미지원. Gemini CLI는 미구현이에요.
- native Files/Interactions/cache/audio/server-side search는 미지원이며 명시적으로 거부해요. native와 Universal의 의미·정확도 동등성을 주장하지 않아요.
- OCR 좌표·object detector 공간 인지, Android 탭/제스처·체크포인트·복구·Trace는 실제 기기에서 확인해야 해요.
- **Helper APK 바이너리는 저장소/wheel에 없어요.** 소스·버전 manifest는 보존해요. 사용자 PC에서 소스를 빌드하거나 호환 Helper를 먼저 설치해야 하며, 번들 자동 설치 성공을 주장하지 않아요. UIAutomator2 fallback은 유지해요.
- Windows fake Python 프로세스 회귀는 실제 Codex 또는 npm `.cmd` launcher 호환성까지 보증하지 않아요.

## 선택된 실행 환경의 수용 검증

```sh
python tools/verify_local_cli.py --allow-live-cli
adb devices
callisto run "설정 앱에서 배터리 화면 확인" --device-serial SERIAL --verification-level final
callisto trace list
```

공식 로그인은 CLI가 관리해요. API 키나 로그인 토큰을 Callisto에 복사하지 않아요.
실제 공급자의 인증 실패·긴 입력·이미지·다중 턴·timeout/취소와 Android 결과 파일을 확인한 뒤
실사용 검증 상태를 갱신해야 해요. 완료된 작업에 검증 항목이 없으면 `test_status=not_reported`예요.

## 브랜치 통합 원칙

작업은 master에 기능별 커밋을 기록한 뒤 main과 조상 관계를 재확인해요.
원래 main `3aa3ccb9a2bc6c8d0e7f70cbd83a59be4e8d5a78`에서 검증된 master로
fast-forward하며 force-push를 사용하지 않아요. main HEAD에서도 동일 CI를 실행해요.
실제 CLI·Android가 미검증인 상태에서의 통합은 코드 정리 버전의 통합이며 실사용 인증이 아니에요.

## v4.2 implementation (2026-10-20 KST)

AI-only image policy, MIME correction, attachment deduplication, OCR coordinate
inverse mapping, content-free real usage reports, paired comparison tooling,
Windows/Linux bootstrap and idempotent setup/check/repair are implemented.
The original Pro graph, prompts, Transcript scrubbing/summary/recall, verification,
recovery and 0/1/2/130 verdicts remain the execution authority. Both preservation
manifests still match exactly (32 + 23 files).

README now starts with setup -> USB approval -> natural-language test. Detailed
configuration and explicit limitations are in advanced-setup.md. The canonical
Skill checks readiness and can resolve its venv Python through install metadata.
The package version is 0.1.2; product workstream is v4.2.

Offline validation passed: full suite 2202 passed / 29 skipped / 8 deselected;
ruff, pip check and frontend-free wheel/isolated installation passed. Subsequent
Skill interpreter-path freshness checks passed the 37-test Skill/setup subset.
Actual Windows setup, Helper SDK build/signature and local Android/CLI before/after
acceptance remain separate checks. Input-token reduction is unknown, not 25%.

main is the code baseline. CI no longer triggers master pushes. master has no
unique commit or open base:master PR; deleting it was attempted but the container
has no GitHub Git credentials and the browser is signed out. The GitHub connector
supports code/ref updates but exposes no branch deletion operation.
