# Callisto 현재 아키텍처

Antigravity CLI (`agy`) supports host registration, explicit selection and managed Skill removal.
Global directory: `~/.gemini/antigravity-cli/skills/callisto/` (separate from IDE/app).
Pro inference with `--ai-cli antigravity` is UNSUPPORTED pending validated non-tool image
input, complete tool blocking, structured output/usage and Android E2E. No provider fallback.
Evidence: [Antigravity integration](maintenance/antigravity-integration.md).

기준: `main`, 2026-10-20. 현재 구조의 기준 문서임. 실행 계약은 `skills/callisto/SKILL.md`, 변경 금지 사항은 `AGENTS.md`에서 관리함. 과거 계획보다 현재 코드·활성 문서가 우선함.

## 실행 경로

1. Codex·Claude Code·Gemini CLI의 Callisto 스킬이 호출 호스트를 확인하고 `callisto setup check --json --ai-cli <host>`로 준비 상태 확인함.
2. 스킬이 `callisto run ... --ai-cli <host>` 호출함. 설치 시 하나의 CLI를 선택·고정하는 구조가 아님.
3. `artemis.interfaces.cli.commands.run.execute_task`와 기존 Pro 그래프가 계획·탐색·조작·검증·복구 수행함.
4. `artemis.services.llm` / `artemis.llm.router`에서 `callisto/llm_adapter/`로 연결함. 기존 에이전트 메시지는 별도 공식 CLI 자식 프로세스에 전달됨.
5. 어댑터의 구조화 응답을 기존 Pro 도구 계약으로 검증·실행함. 모델 CLI 자체가 Android 조작을 수행하지 않음.
6. 원본 Trace·체크포인트·캡처를 유지하고 `callisto.verdict`와 `callisto.usage`에서 판정 및 사용량 기록함.

호스트의 대화 세션이나 일시적 모델 선택은 자식 CLI에 자동 상속되지 않음. 자식은 공식 CLI의 사용자 기본 설정·로그인을 사용함. Callisto가 모델·추론 수준을 강제하거나 API Key로 직접 모델을 호출하지 않음.

## 보존 경계

| 경로 | 현재 역할과 보존 이유 |
| --- | --- |
| `callisto/` | CLI, 설치·스킬, 설정, 전송 어댑터, 이미지, OCR 경계, 판정·사용량 |
| `artemis/graph/`, `artemis/agents/` | 원본 Pro 실행 순서·프롬프트·계획·탐색·검증·복구 |
| `artemis/mcp/` | Pro 내부 in-process FastMCP 액션 세션. 외부 MCP 서버가 아님 |
| `artemis/agents/flash/` | Pro 공유 요약·압축과 프롬프트 계약 회귀 자산. 독립 Flash 러너는 없음 |
| `third_party/mobile_use/` | 기존 SDK·드라이버·유틸리티 및 라이선스 |
| `config/artemis.jsonc` | 소스 작업 공간의 설정. `artemis/resources/config/`는 독립 설치 기본값 |
| `packages/artemis-accessibility-helper/` | Helper 소스, 개발 서명 키, manifest 및 선택적 빌드 APK |
| `skills/callisto/SKILL.md` | 유일한 스킬 원본. `.agents/skills/callisto/SKILL.md`는 발견용 포인터 |
| `tools/`, 루트 `setup.*` / `uninstall.*` | 설치 bootstrap, 검증·승인 기반 소스 설치 제거, Helper 빌드, 실제 수용 검증 및 wheel 검증 |
| `tests/unit/`, `tests/callisto/`, `tests/tools/` | 현재 오프라인 회귀. 원격 SDK mock 계약도 별도 기본 수집됨 |
| `tests/integration/`, `tests/e2e/` | 명시적 환경·기기 검증. 기본 회귀의 통과와 구분함 |
| `tests/upstream_removed/` | 제거된 기능의 원본 테스트 이력. 현재 회귀가 아님 |

Explorer의 `flash` 탐색 tier는 독립 Flash 프로필과 다르며 유지됨. 원본 core 32개 및 engine 23개의 SHA-256은 두 보존 manifest와 회귀에서 검증함. 보존 근거는 [원본 기준선](upstream-baseline.md) 참조.

이미지 최적화는 모델에 보내는 첨부에만 적용됨. 원본 캡처·Trace·XML과 Pro 정규화 좌표는 유지됨. CLI OCR의 전송 픽셀 좌표만 원본 크기로 역변환함. 정책 값·제약은 [고급 가이드](advanced-setup.md#이미지-안전-경계와-계측) 참조.

## 호환성 경계

- `artemis` CLI 별칭, 내부 모듈명, `_legacy_imports.py`의 import 별칭 및 저장된 경로·진단 ID 유지됨.
- 원격 SDK `artemis_client`는 `artemis.interfaces.sdk.client`와 공개 export가 참조하므로 보존됨. Callisto는 HTTP Daemon을 제공하지 않음.
- 루트 `artemis_client/`는 기존 소스 직접 실행에 사용됨. wheel과 독립 SDK 패키지는 `packages/artemis-client/src/artemis_client/`를 사용함. 동일한 6개 파일을 임의로 제거·이동하지 않음.
- `scripts/setup.ps1`은 폐기 예정 경고 후 루트 설치기로 위임하는 호환 경로임. 기존 `-Python`은 명시적으로 거부함. 공식 설치 진입점은 루트 `setup.ps1` / `setup.sh`임.
- `mcp<2`는 내부 FastMCP v1 계약에 필요함. `google-genai`는 native 데이터형에 필요함. `httpx`는 기존 perception/OCR 시그니처와 테스트에서 사용됨.
- Android 패키지 `com.artemis.helper`, 서비스 ID와 APK 파일명은 설치 호환용임. UIAutomator2 fallback 유지됨.
- `helper/ArtemisAccessibilityHelper.apk`는 canonical bundle이 아니며 canonical manifest 해시와 다름. 과거 APK를 복사하거나 manifest를 바꿔 검증된 번들로 만들지 않음. 외부 번들 경로는 기존 `CALLISTO_HELPER_DIR` 사용함.

호환성 제거는 별도 작업에서 지원 대상·이관 절차를 확인한 뒤 수행해야 함. 미사용으로 단정할 수 없는 공개 API와 원본 엔진 소스는 유지함.

## 문서 역할과 우선순위

| 문서 | 책임 |
| --- | --- |
| `README.md` | 사용자 설치, 자연어 실행, Helper 권한 문제 해결 |
| `AGENTS.md` | AI 작업 규칙·변경 금지·검증 요구 |
| `skills/callisto/SKILL.md` | 스킬의 실제 호출·준비 확인·판정 계약 |
| `docs/architecture.md` | 현재 구조와 보존·호환성 경계의 기준 |
| `docs/advanced-setup.md` | 수동 설치·설정 우선순위·운영·이미지 상세 |
| `docs/cli-capability-matrix.md` | 구현된 지원 범위와 검증 한계 |
| `docs/migration-status.md` | 현재 전환 상태와 최신 검증 증거 링크 |
| `docs/upstream-baseline.md`, `docs/upstream-*-manifest.json` | 원본 출처·보존 범위·고정 해시 |
| `docs/maintenance/` | 정리 조사·파일별 판정·검증 증거. 실행 지침이 아님 |
| `docs/archive/` | 과거 계획·보고서. 현재 사용법이나 모델 선택 지침이 아님 |

실행·기능 관련 변경 시 해당 활성 문서를 갱신함. 과거 기록을 최신 문서에 이어 붙여 현재 상태와 혼합하지 않음.
