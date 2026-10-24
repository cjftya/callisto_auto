# Callisto 현재 아키텍처

Antigravity CLI (`agy`) supports host registration, explicit selection and managed Skill removal.
Global directory: `~/.gemini/antigravity-cli/skills/callisto/` (separate from IDE/app).
Pro inference with `--ai-cli antigravity` is UNSUPPORTED pending validated non-tool image
input, complete tool blocking, structured output/usage and Android E2E. No provider fallback.
Details: [CLI capability matrix](cli-capability-matrix.md).

현재 `main` 기준. 현재 구조의 기준 문서임. 실행 계약은 `skills/callisto/SKILL.md`, 변경 금지 사항은 `AGENTS.md`에서 관리함. 과거 계획보다 현재 코드·활성 문서가 우선함.

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

DataEngine 저장 스레드의 등록·시작·정리·스냅샷은 같은 락을 사용하며, 락 밖에서 완료를 기다리고 해당 작업이 생성한 후속 저장도 비워질 때까지 대기함. 종료 호출자는 무관한 새 생산 작업을 먼저 중단해야 함. 동시성 회귀 테스트는 `tests/unit/data_engine/test_background_threads.py`에서 유지함.

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
| `docs/upstream-baseline.md`, `docs/upstream-*-manifest.json` | 원본 출처·보존 범위·고정 해시 |

실행·기능 관련 변경 시 해당 활성 문서를 갱신함. 과거 계획과 검증 보고서는 Git 이력에서 확인하며 활성 문서에 혼합하지 않음.

## Operator 문맥 계측과 선택적 비용 정책

`CLIChatModel`은 공급자 원본 usage와 정규화된 logical/uncached/cache-read/cache-write/output,
usage scope를 분리한다. CLI 실행 전체 합계를 마지막 모델 요청의 문맥 크기로 가정하지 않는다.
요청/단일 요청임이 확인된 usage만 기존 context gate에 전달하고, 나머지는 기존 추정 경로를 사용한다.
본문·stdin·이미지 바이트와 영역별 S/D/H/O/R/unknown 계측은 토큰 수가 아니다.
run/agent invocation/observation/logical loop/attempt 식별과 provider lock 대기 시간을 기록하며,
반복 원인은 구조적 tool result/error만 확정하고 다른 원인은 unknown으로 남긴다.

`memory.transcript.context_policy`는 `off`(기본), `shadow`, `ready_only`를 지원한다.
기존 TranscriptLedger가 유일한 기준이며 Context IR은 변경 불가능한 출처/transaction 스냅샷이다.
Shadow는 기존 송신을 유지한다. Ready-only는 오래된 완료 turn의 연속 ready prefix에서
coverage·도구 pair·최근 floor·원본 이미지·오류·바이트 이득을 확인한 뒤 송신 view만 교체한다.
원문 active span을 freeze하지 않으므로 비용 view 자체는 즉시 해제할 수 있다.
기존 start/soft/hard, 요약 생성 cadence, 이미지 depth와 CLI 모델 선택은 유지한다.

EvidenceRegistry는 원본 asset과 관측별 evidence를 구분하고 current/comparison/recalled/
historical/overlay/unknown, summary 상태, 원본/전송 geometry와 명시적 pin을 관리한다.
조회 증거는 공유 ledger의 commit hook에서 정상 dispatch·닫힌 tool transaction·성공한 조회 결과·
그 이후 AI 판단을 모두 확인한 경우에만 해당 decision pin을 해제한다. 오류·중단·미완료·
unknown/comparison/overlay 소유권은 추정하지 않는다. 실패 실행은 step별 incident pin을 추가하며,
후속 dispatch만으로 원래 의도 달성을 단정하지 않아 명시적 incident 해제 이벤트를 기다린다. 현재 ephemeral 안내가
있으면 조기 압축을 보류하며 opt-in에서 보호 증거가 hard fold를 막으면 명시적 자원 오류를 낸다.
이는 기존 비상 압축을 비용 최적화로 재해석하는 것이 아니라 증거 유실을 막는 opt-in 제한이다.
DataEngine 원본과 기존 search/replay/screenshot 조회는 변경하지 않는다.

실제 공급자/Android 수용 전에는 기본 활성화하지 않는다. C의 CLI 세션 재사용은 구현하지 않았다.


2차 비용 후보는 `CALLISTO_OPERATOR_IMAGE_POLICY=off|shadow|ready_only`와
`CALLISTO_COMPACT_TEXT=1`로 각각 선택한다(둘 다 기본 off).
이미지 view는 최근 최소 5 turns·현재 loop·열린 transaction·오류·ephemeral 안내·pin·
비-historical 역할·미완성 summary를 보존한다. 안전한 오래된 historical 이미지에 한해
기존 ready visual summary로 **송신 사본**을 대체하며 원본 ledger/DataEngine은 그대로다.
단일 순수 text block만 문자열로 표현하는 codec은 명시적 opt-in이고 tool ID/status/name과
추가 block metadata를 유지한다. 정책 조합의 실제 행동 동등성은 PC 수용 대상이다.

역할별 첨부 바이트는 실제 첫 첨부 역할에 한 번만 귀속하며 공유 참조는 별도 집계한다.
필수 current 고유 자산과 추가 첨부, 같은 자산/다른 evidence, observation별 재노출,
S/D/H/O/R 재전송 바이트·history 종류를 구분한다. 해시·픽셀·본문은 계측에 저장하지 않는다.
반복 바이트는 캐시 적중이나 토큰 수를 의미하지 않는다. 여러 공급자가 섞인 정규화 합계는
null이고 `by_provider`에서만 합산한다.
