# Callisto v4.0 — CLI 전용 최종 정리 및 `main` 통합 계획서

- **작성일:** 2026-10-19
- **저장소:** https://github.com/cjftya/callisto_auto
- **작업 모델:** GPT-6.1 SOL **High** (코드 수정·검토 담당 모델)
- **작업 브랜치:** `master` → 검증 후 `main`
- **현행 기준:** `master` = `c56d3c7fef578d9e8e2339a410b43ee82cad05d2` / `main` = `3aa3ccb9a2bc6c8d0e7f70cbd83a59be4e8d5a78`
- **기준 문서:** `docs/plan-v3.0.md`, `docs/migration-status.md`, `docs/cli-capability-matrix.md`, `AGENTS.md`
- **작업 성격:** 신규 에이전트 개발이 아닌 **전환 마무리·잔재 제거·계약 검증·브랜치 통합**

> **핵심 원칙:** ARTEMIS Pro의 계획·관찰·조작·검증·복구·Trace 동작은 유지하고, **AI 모델 추론은 설치·인증된 로컬 AI CLI만 호출**한다. 사용자에게 노출되는 실행 경로는 **Callisto CLI 및 AI CLI Skill**로 제한한다. 검증하지 않은 기능을 성공으로 표시하지 않는다.

## 1. 최종 목표와 변경 금지선

**반드시 달성할 상태**

1. 모든 운영용 AI 추론 경로는 `callisto/llm_adapter/` 또는 해당 경계의 검증된 로컬 CLI 호환 포트만 사용한다. 애플리케이션이 직접 LLM/VLM 클라우드 SDK·REST API·API 키를 사용해서는 안 된다.
2. `callisto run`, `callisto doctor`, `callisto trace`, `callisto helper` 및 `skills/callisto/SKILL.md`를 공식 사용자 인터페이스로 정리한다. 웹 UI, 관리자 콘솔, HTTP daemon, 외부 MCP 서버와 외부 MCP 실행 명령은 제공하지 않는다.
3. ARTEMIS 기존 **Pro 그래프와 에이전트**, 스크린샷/XML·좌표·제스처, ADB, Accessibility Helper, 상태/체크포인트/복구, 테스트 판정·Trace를 유지한다.
4. Flash **실행 프로필**만 제거한다. Pro 내부의 Explorer `flash` 탐색 tier 및 Pro가 공유하는 summarizer/compressor는 기능이 실제 사용되는 한 보존한다.
5. 남은 코드·리소스·테스트·설정·의존성을 실제 import/호출 관계로 분류해 정리하고, 설치 가능한 독립적인 CLI 패키지를 만든다.
6. 작업 결과를 먼저 `master`에 커밋·푸시하고, 아래 승인 관문을 통과하면 `main`에 **기록을 유지하는 방식으로** 통합한다.

**절대 금지**

- Planner/Operator/Explorer/Validator/Checker 등을 Skill 내 단순 프롬프트나 새 `observe → tap` 루프로 교체하지 않는다.
- 기존 Pro 내부 알고리즘, 프롬프트, 검증 기준, 복구 정책을 정리 명목으로 임의 재설계하지 않는다.
- API 키 또는 CLI 로그인 토큰을 읽어 직접 API 호출로 우회하지 않는다.
- 원본의 미지원 native Files/Interactions/cache/audio/search를 가짜 성공·가짜 메타데이터로 대체하지 않는다.
- `main`에 직접 개발 커밋하거나 force-push하지 않는다. 검증 실패 상태를 숨겨 병합하지 않는다.

### 내부 MCP에 대한 명확한 경계

`artemis/mcp/action_session.py`, `artemis/mcp/action_server.py`는 **기존 Pro 내부의 메모리 기반 Android 액션 세션**이다. 외부 MCP 서버가 아니며, 현재 Pro 실행 계약에 관여한다. **v4.0 필수 작업에서는 우선 보존**하고 외부 노출·stdio/server entrypoint만 완전히 차단한다. `mcp` 패키지까지 없애려면 액션 이름, JSON Schema, 오류, 시간제한, 취소, 동시성, Trace 계약을 동일하게 보장하는 **별도 동등성 검증이 먼저** 필요하다. 검증되지 않은 전체 제거는 금지한다. Android Helper가 기기 내부에서 사용하는 루프백 통신도 웹 UI로 간주하지 않는다.

## 2. 현재 `master`에서 확인된 잔여 항목

| 대상 | 현재 사실 | v4.0 조치 |
|---|---|---|
| `callisto/llm_adapter/` | Codex CLI 어댑터 구현, 실제 공급자 검증 전 | CLI 옵션·JSON/tool/이미지/취소/Windows 프로세스 동작 재검증 |
| Claude / Gemini CLI | Claude 텍스트 실험 단계, Gemini 미구현 | 공식 지원 범위를 검증해 구현하거나 명시적 미지원으로 고정. **Codex 완료와 구별** |
| `artemis/llm/router.py` | `provider='cli'` 외 직접 API 거부 | 모든 우회 호출점을 재감사하고 회귀 테스트 추가 |
| `artemis/agents/video_analyzer/` | 로컬 native 포트로 전환했지만 Google API 키 확인 분기·native File 코드가 남음 | 키 존재 여부에 따른 경로 차이 제거. 프레임 기반 대체·명시적 오류 검증 |
| `artemis/utils/ocr_api.py` | CLI OCR 포트 사용, 과거 HTTP 응답 파서 잔존 | 호출 관계 확인 후 안전하게 분리/삭제. 좌표 정확도는 실기기 검증 |
| `config/artemis.jsonc` | 기본 공급자는 CLI이나 일부 전용 모델 ID에 Gemini 이름 잔존 | 실제 호출/라벨·설정의 의미를 확인하고 CLI 일관성 정리 |
| `artemis/resources/showcase_ui/` | 브라우저 정적 리소스가 저장소에 잔존 | 런타임 참조가 없음을 확인하고 삭제. wheel에도 미포함 확인 |
| `pyproject.toml` | `google-genai`, `mcp`, `langchain-mcp-adapters` 등의 의존성 존재 | **무조건 삭제 금지**. 실제 사용 여부 검사: `google-genai` types, 내부 MCP 등 필요한 의존성은 유지 |
| `artemis/config/` | 과거 API 키/MCP/서버 상수·명칭 잔존 | 런타임 사용 여부 감사 후 제거/비활성화. 레거시 alias는 호환성 판단 후 처리 |
| `tests/upstream_removed/` | 제거된 웹/Flash/외부 MCP 테스트가 보관됨 | 활성 테스트와 분리 유지할 가치 판단. 필요한 회귀는 이관하고 불필요한 보관 파일은 정리 |
| `skills/callisto/` 및 `.agents/skills/callisto/` | 유사한 두 Skill 경로 존재 | 표준 문서를 단일 소스로 관리하고 설치/탐색 호환성을 검증 |
| `.github/workflows/offline.yml` | `master` push와 PR만 검증 | `master`/`main` 및 PR 모두 테스트, Linux/Windows, wheel·의존성 확인 |
| `main` | 초기 커밋 상태, `master`가 2커밋 앞섬 | 최종 단계에서 차이를 다시 확인 후 안전하게 fast-forward 또는 PR 병합 |

**주의:** 파일명에 `mcp`, `google`, `flash`, `web`가 등장한다고 모두 제거 대상으로 보지 않는다. **실행 경로와 실제 네트워크 호출을 기준**으로 판정한다. 원본 라이선스/NOTICE, 원본 보존 manifest와 추적 가능한 기준 SHA는 유지한다.

## 3. 단계별 실행 계획 (GPT-6.1 SOL High)

### P0 — 기준점 고정과 정적 감사

1. `master`, `main` 최신 SHA를 다시 읽고 작업 시작 기준을 기록한다. `main`의 동시 수정이 있으면 병합 전략을 새로 계산한다.
2. `docs/upstream-preserved-manifest.json`로 Pro의 핵심 파일 SHA를 확인하고 기존 오프라인 테스트 결과를 기준선으로 확보한다.
3. 전체 import/call graph에서 실제 AI 호출, API 키 참조, Google native Files/Interactions, HTTP 클라이언트, MCP 서버, 브라우저 리소스, Flash profile 실행 경로를 찾는다.
4. 분류표 작성: **유지 / CLI 교체 / 제거 / 런타임에서 사용하지 않는 호환 코드 / 공식 미지원**.
5. 각 제거 후보에 대응하는 테스트를 먼저 선정한다. 근거 없는 대량 삭제는 금지한다.

**완료 기준:** 파일별 조치·근거·영향·테스트가 기록된 감사 보고서가 있음.

### P1 — AI 추론 경계의 완전 단일화

1. `ModelFactory`, `get_llm`, `get_google_llm`, native GenAI-shaped 포트와 영상/이미지/OCR/메모리 압축·서브에이전트까지 **모든 실제 추론 진입점**을 조사한다.
2. 일반 AI 판단이 직접 SDK 클라이언트 또는 HTTP 요청으로 나가지 못하도록 실행 경계에서 차단한다. `google.genai.types`처럼 **직접 네트워크 호출이 없는 데이터 형식**은 필요할 때만 남긴다.
3. 영상/이미지 처리에서 과거 Google API 키 유무에 따라 알고리즘이 달라지는 분기를 제거하고, CLI에서 가능한 기존 Universal 프레임 경로를 사용한다. 해당 경로의 기능 동등성은 별도로 테스트한다.
4. native 파일 업로드/캐시/음성/검색 등 CLI로 동등하게 제공할 수 없는 기능은 기능별 `UnsupportedCapability`로 분리하고, 호출자에게 정확한 이유를 반환한다.
5. 텍스트·이미지·JSON Schema·function/tool call·메시지 이력·툴 결과 왕복·timeout·cancellation·비정상 출력에 대한 **fake CLI 계약 테스트**를 확장한다.
6. 모델명을 `gemini-*`로 기록한 내부 설정은 실제 실행 모델 선택에 반영되는지 확인하고, 사용되지 않는 고정 문자열/설정을 정리한다. 실행 모델의 기본값은 별도 요청이 없다면 임의로 바꾸지 않는다.

**완료 기준:** 활성 경로에서 **직접 AI API 요청 0건**. CLI 실패/미지원 기능은 명확한 오류로 나타나며, 테스트에서 확인됨.

### P2 — CLI 공급자·Skill 정리

1. **Codex CLI를 필수 지원 대상**으로 삼아 headless 호출, JSON 출력, image attachment, tool result, 기존 컨텍스트 전달 방식이 **공식 인터페이스와 맞는지 사용자 PC에서** 검증 가능한 상태로 정리한다.
2. Claude Code와 Gemini CLI는 별도 capability matrix를 유지한다. 지원하는 공식 기능만 구현하고, 이미지·도구 호출 등 필수 기능이 빠지면 전체 Pro E2E 지원 공급자라고 표시하지 않는다.
3. 공급자의 도구 실행 기능(shell·plugins·MCP)과 **ARTEMIS의 구조화된 Android 액션 출력**을 엄격히 분리한다. 공식 CLI 정책·인증을 우회하지 않는다.
4. Skill 설명을 `skills/callisto/SKILL.md`에 일원화하고 `.agents/skills/callisto/`가 참조하거나 동기화되는 형태로 문서 드리프트를 방지한다.
5. `doctor`는 설치/경로/설정만 검사한다는 점을 명시한다. 인증 성공이나 실추론 성공을 추정하지 않는다.

**완료 기준:** 지원 공급자와 미지원 공급자가 명확히 구분되고, Skill이 기존 Pro 엔진을 호출하며 자체 에이전트로 바뀌지 않음.

### P3 — 레거시 소스·설정·의존성·패키징 정리

1. `artemis/resources/showcase_ui/` 등 실제 참조되지 않는 웹 정적 산출물을 제거한다.
2. 브라우저·HTTP daemon·외부 MCP·Flash **실행** 관련 코드/테스트/설정/진입점이 존재하지 않거나 비활성 경로에만 보관되는지 확인한다. 공식 CLI `--help`에 노출되어서는 안 된다.
3. 원본 패키지와 테스트를 기준으로 미사용 직접 API 키/웹 SDK 의존성을 제거하되, **내부 MCP 액션 세션 및 Google 타입 모델에 필요한 패키지는 유지**한다.
4. 이전 제거 테스트 폴더의 필요한 계약 검사를 활성 테스트로 이관한다. 근거와 이력 없이 원본 기능 관련 테스트를 없애지 않는다.
5. Linux·Windows의 clean venv에서 editable 설치, wheel 설치, CLI 도움말, Pro import, 설정 로딩, APK Helper 자료 포함 여부를 검증한다.
6. CLI 설치 시 프런트엔드 빌드·클라우드 API 키·별도 MCP 서버가 필요 없는지 검증한다.

**완료 기준:** 필수 패키지 외 불필요한 웹/외부 서버 런타임 의존성이 없고, CLI-only wheel이 독립 설치됨.

### P4 — 회귀·보안·플랫폼 검증

**Work/CI에서 허용되는 검증**

- `CALLISTO_FORBID_LIVE_CLI=1 python -m pytest` 전체 회귀
- `python -m pip check`, wheel 빌드/격리된 설치 및 smoke test
- Linux/Windows fake subprocess·프로세스 트리 종료·타임아웃·취소
- 직접 API provider 거부, credentials 비노출, 미지원 기능 명시적 실패
- `master`와 `main`의 GitHub Actions 워크플로 경로 확인
- 보존 manifest의 Pro 핵심 알고리즘/프롬프트 변경 여부 확인

**선택된 CLI 실행 환경에서 실제 검증할 항목**

- 실제 인증된 `codex`로 `python tools/verify_local_cli.py --allow-live-cli`
- 텍스트/이미지/JSON/tool calls/다중 턴/인증 실패/긴 입력/취소/timeout
- Android 연결 `adb devices`, 자연어 테스트 `callisto run "설정 앱에서 배터리 화면 확인" --device-serial SERIAL --verification-level final`
- 실제 스크린샷, XML, 좌표, 탭/입력, 결과/체크포인트/복구/Trace
- 필요하다면 실제 Windows 실행에서 자식 프로세스 종료 검증

**통과 기준:** 테스트 숫자·skipped·환경·실행 커밋·결과 파일을 기록한다. 모의 응답 통과를 실제 모델/Android 성공으로 오인하지 않는다.

### P5 — 문서 마감, `master` 반영 및 `main` 통합

1. `docs/migration-status.md`, `docs/cli-capability-matrix.md`, `README.md`, `AGENTS.md`를 실제 근거에 맞춰 수정한다. 미지원 범위·실사용 미검증을 명시한다.
2. 각 단계의 변경을 `master`에 기능 단위 커밋으로 나누고 푸시한다. 다른 사람이 변경한 부분은 임의 덮어쓰지 않는다.
3. `master` HEAD 기준 GitHub Actions의 Linux/Windows 회귀 및 wheel 결과를 확인한다. 실패가 있으면 수정 후 재검증한다.
4. `main`과 `master`의 선후관계, 공통 조상, 변경 파일을 다시 비교한다. 필요하면 통합 직전 보호 태그 또는 커밋 SHA를 기록한다.
5. 통과된 `master`를 `main`에 PR 또는 **fast-forward**로 반영한다. **force-push, 이력 손실, 미검증 직접 교체 금지**.
6. `main` 푸시 후 동일 테스트를 다시 돌리고, `main`에서의 `callisto --help`, 패키징 및 중요 기능의 최종 상태를 확인한다.
7. 최종 결과 보고서에 `master`/`main` SHA, 변경 파일, 삭제 범위, 테스트 증거, 지원·미지원 기능, 남은 실기기 검증을 명시한다.

**병합 원칙:** 정적/오프라인 검증이 모두 통과하더라도 실 CLI·Android 검증이 안 됐다면 **"코드 정리 완료, 실사용 검증 미완료"**로 기록한다. 완전한 실사용 완료로 발표할 수 없다. 실기기 검증까지 반드시 끝내야 하는 릴리스라면 사용자 PC 검증 증거를 받은 뒤 `main`에 통합한다.

## 4. 완료 판정표 (Definition of Done)

| 구분 | 필수 통과 조건 |
|---|---|
| 추론 단일화 | 운영 경로 직접 AI API 호출 없음; Codex CLI 계약 테스트 통과 |
| 기능 보존 | 기존 Pro 에이전트/그래프/상태/복구/Trace의 핵심 회귀 통과 |
| 인터페이스 | 사용자 인터페이스 CLI/Skill 전용, 웹·HTTP daemon·외부 MCP 진입점 없음 |
| Flash | Flash 실행 프로필 접근 거부, Pro 공유 Explorer tier 유지 |
| 오류 처리 | 미지원 기능·인증 실패·timeout·취소에 가짜 성공 없음 |
| 코드 품질 | 필요 없는 웹 리소스·키 기반 분기·테스트/의존성 정리됨 |
| 이식성 | Linux/Windows 오프라인 CI, clean install/wheel, `pip check` 통과 |
| 실사용 | 사용자 PC에서 실제 CLI와 Android E2E 증거 확보 또는 **미검증 표시** |
| Git | `master` 커밋·푸시 → 비교/CI → 안전한 `main` 통합, 양쪽 HEAD 보고 |
| 문서 | README/Skill/지원 매트릭스/마이그레이션 최종 보고가 실제 코드와 일치 |

## 5. 권장 커밋 순서

```text
chore: audit CLI-only boundaries and capture final migration baseline
refactor: remove remaining direct AI API and credential-dependent branches
test: harden CLI inference and unsupported-native contracts
refactor: prune web assets and unused legacy dependencies
chore: consolidate Callisto skill and CLI documentation
ci: validate master and main on Linux and Windows
fix: resolve Pro regression and packaging failures
docs: publish Callisto v4 migration and capability report
```

각 커밋은 좁은 범위로 만들고 `main` 통합 전 변경 사항을 전수 확인한다.

## 6. SOL 6.1 High 작업 지시문 (그대로 전달)

> `cjftya/callisto_auto`의 최신 `master`에서 Callisto v4.0 최종 정리를 수행해 주세요. **작업 모델은 GPT-6.1 SOL High**입니다. 기존 ARTEMIS Pro의 그래프·Planner/Operator/Explorer/Validator/Checker 등 에이전트, 프롬프트, 체크포인트, 복구, ADB/Helper, Trace 및 결과 판정은 최대한 그대로 유지해 주세요. 모든 AI 추론을 공식 로그인된 로컬 AI CLI 어댑터를 통해서만 처리하도록 전체 실행 경로를 감사하고, 남아 있는 직접 AI API 호출·API 키 의존 분기·웹 UI/HTTP daemon·외부 MCP·Flash 실행 프로필·불필요한 웹 산출물 및 의존성을 안전하게 정리해 주세요. 단, **Pro 내부 in-process MCP 액션 세션과 Explorer의 `flash` 탐색 tier는 외부 실행 프로필과 구별해 계약이 깨지지 않도록 보존**해 주세요. 미지원 native 기능은 오류로 명확히 표시하고 가짜 성공 처리는 금지합니다. 오프라인 회귀는 fake CLI 및 Linux/Windows 테스트·패키징으로 검증하고, 실제 CLI 및 Android E2E는 공식 CLI와 기기가 연결된 선택된 실행 환경에서 수행합니다. 각 단계별로 변경을 검증해 `master`에 커밋·푸시하고, `main`과의 최신 차이를 재확인한 뒤 테스트 관문을 통과했을 때 PR 또는 fast-forward 방식으로 `main`에 통합해 주세요. 미검증 항목이 있다면 실제 검증 완료라고 보고하지 마세요. 최종 커밋 SHA, 테스트, 미지원 기능, 남은 위험을 상세히 보고해 주세요.

---

**상태:** 본 문서는 **작업 계획서**입니다. 작성 자체로 `master` 또는 `main`에 코드 변경·병합이 이루어지는 것은 아닙니다.
