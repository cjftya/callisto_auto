> **과거 기록 — 현재 구현 지침이 아님.** 작성 당시의 모델·설치·지원 상태이며, 현재 기준은 [아키텍처](../architecture.md), [지원 범위](../cli-capability-matrix.md), [전환 현황](../migration-status.md)임.

# Callisto — ARTEMIS AI API → AI CLI 전환 계획서 v3.0

> **핵심 원칙:** ARTEMIS의 내부 에이전트·테스트 기능과 Pro 실행 흐름은 유지한다. **AI 모델을 직접 호출하던 API 계층만, 설치·인증된 AI CLI를 호출하는 어댑터 계층으로 교체한다.** 사용자용 웹 UI와 외부 MCP 서버는 제외한다.

| 항목 | 내용 |
|---|---|
| 프로젝트 | Callisto (`callisto_auto`) |
| 기본 개발 모델 | GPT-6.1 SOL Medium |
| 원본 저장소 | https://github.com/google/artemis |
| 목표 저장소 | https://github.com/cjftya/callisto_auto.git |
| 기준 원본 | `google/artemis` `main` — `351ca8422f7b5b54e80a9c1ce03a222e02415b6b` (2026-10-19 확인) |
| 목표 브랜치 | `main` (검증 후 반영) |
| 구현 방식 | **기존 ARTEMIS + CLI LLM Adapter + Callisto CLI/Skill** |
| 작성일 | 2026-10-19 |

## 1. 프로젝트 목표와 절대 변경 금지 원칙

Callisto는 Google ARTEMIS의 Android 자동 테스트 프레임워크를 바탕으로, **기존 모델 API 키를 사용하는 추론 호출을 AI CLI를 통해 처리**하도록 전환하는 프로젝트다. 사용자 입장에서는 Codex CLI, Claude Code, Gemini CLI 등의 인증·실행 환경을 활용해 ARTEMIS의 기존 Pro 자동 테스트를 수행한다.

**보존 대상 — 동작 알고리즘과 계약을 기본적으로 유지**

- Planner / Operator / Explorer / Validator / Checker / Diagnoser / Summarizer / Outputter 등 기존 에이전트의 책임과 처리 흐름
- Pro 실행 그래프, 상태 관리, 서브태스크, 화면 인지, 도구 호출 및 실패 복구 방식
- 화면 캡처, UI 계층 파싱, 좌표·제스처, ADB 제어, Accessibility Helper
- 테스트 기록, 체크포인트, 검증·리포트·추적(Trace) 데이터
- 기존 JSON·구조화 응답, 메시지, 도구 호출 등 에이전트와 모델 사이의 **논리적 인터페이스**

**교체·제거 대상 — 경계 밖의 통신/배포 계층만 수정**

- Google/OpenAI/Anthropic 등 API 키 기반 직접 LLM/VLM 호출 → 인증된 AI CLI를 이용하는 **LLM Adapter**
- 공급자별 직접 SDK 호출 지점 → 공통 어댑터 경유 (특히 native Gemini 경로)
- 사용자용 Angular 웹 UI, 관리자 콘솔, 웹 대시보드, 웹 Daemon 및 웹 전용 빌드 의존성 → 제거
- 외부 도구 연결용 `mcp_server/` 및 외부 MCP CLI 명령 → 제거
- Flash **실행 프로필** → 제거, Pro만 유지. 단 **Pro 내부 Explorer의 `flash` 탐색 tier는 별도 개념**이므로 혼동하여 제거하지 않는다.

**금지:** Planner/Operator/Explorer/Checker를 삭제하거나 Skill로 대체하지 않는다. AI 판단 로직을 새로 만들지 않는다. 기존 Pro 그래프를 단순 `observe → tap` 반복기로 재작성하지 않는다.

## 2. 확인된 원본 구조와 수정 지점

다음은 실제 원본 저장소 기준으로 확인한 위치다. 코드 이관 전 최신 상태와 동일한지 다시 확인한다.

| 소스 | 조치 | 확인할 사항 |
|---|---|---|
| `artemis/graph/`, `artemis/agents/` | **보존** | Pro 노드/상태, 검증·복구 유지 |
| `artemis/services/llm.py` | **최소 수정** | 기존 `get_llm`, 구조화 추론 및 재시도 계약 유지 |
| `artemis/llm/router.py` | **어댑터 연결** | 모델 선택과 기존 `BaseChatModel` 연동 |
| `artemis/llm/google/`, `artemis/agents/explorer/` | **직접 호출 감사** | Gemini native 경로, 멀티모달 및 tool calling |
| `artemis/agents/video_analyzer/`, 이미지/로그 관련 에이전트 | **직접 호출 감사** | 별도 Google SDK·VLM 호출 전수 검사 |
| `artemis/interfaces/cli/commands/run.py` | **기본 실행 수정** | 웹 Daemon 자동 실행 경로 제거; 로컬 standalone 기본화 |
| `artemis/interfaces/cli/main.py` | **정리** | `run/doctor/trace` 등 필요한 CLI만 노출 |
| `artemis/sdk/`, `artemis/config/`, `artemis/runtime/` | **선별 수정** | API 키 검증·모델 사전 연결·웹 서비스 의존성 정리 |
| `artemis/mcp/` | **원칙적으로 보존** | Pro 내부의 **in-process 액션 세션**. 별도 MCP 서버 실행과 다름 |
| `mcp_server/` | **제거** | 외부 MCP 서버·도구 등록 계층 |
| `apps/showcase_ui/`, `apps/admin_console/` | **제거** | 사용자 웹 UI/관리자 API |
| `packages/artemis-accessibility-helper/` | **보존** | 기기 내부 Helper와 로컬 ADB 연동 |
| `third_party/mobile_use/` | **필요 코드 유지** | 기반 SDK/도구/런타임 의존성 |
| `pyproject.toml`, `setup.py` | **패키징 수정** | 불필요한 AI API·웹 패키지 정리, UI 빌드 필수 조건 제거 |
| `tests/` | **보존·확장** | 기존 Pro 회귀 테스트와 CLI Adapter 테스트 |

**주의 1 — 내부 MCP:** ARTEMIS의 `artemis/mcp/action_session.py`는 메모리 내부에서 Android 액션을 중개한다. 이는 외부 프로세스를 띄우는 `mcp_server/`와 다르다. **내부 기능 보존이 우선**이므로 최초 이관에서 제거하지 않는다. 추가로 “모든 내부 MCP 패키지까지 제거”하는 작업은 명시적으로 별도 범위를 승인받기 전까지 하지 않는다.

**주의 2 — Accessibility Helper:** 기기 내부 루프백 통신은 웹 UI/웹 서비스와 구분한다. Android 화면 관찰에 필요한 내부 전송 방식은 보존한다.

## 3. 목표 실행 아키텍처

```text
사용자 자연어 테스트 요청
         │
AI CLI (Codex / Claude Code / Gemini CLI)
         │  Callisto Skill 또는 터미널 명령
         ▼
Callisto CLI 엔트리포인트
         │
ARTEMIS 기존 Pro Graph / Agents (수정 최소화)
         │  기존 get_llm(), invoke/ainvoke, structured output 계약
         ▼
Callisto LLM Adapter  ← 유일한 AI 통신 교체 영역
         │  CLI 비대화형 실행 / 입력·출력 직렬화 / 인증된 로컬 CLI
         ▼
모델 제공 CLI 실행 환경 (Codex · Claude · Gemini)
         │
ARTEMIS Pro Agents ← 응답 반환 / 검증 / 다음 단계
         │
기존 Android 제어 (ADB / Accessibility Helper / 내부 액션 세션)
         ▼
Android 기기 / 에뮬레이터
```

**매우 중요한 구분:** 호스트에서 이미 실행 중인 AI CLI의 **동일한 대화·모델 세션을 내부 Python 엔진이 직접 호출할 수 있다는 보장은 없다.** 일반 Skill은 연결 지침이지 Python에 모델 추론 API를 제공하지 않는다. 우선 인증된 AI CLI의 **공식 비대화형 실행 인터페이스**로 호출 가능한지 검증한다. 이 방식은 보통 별도 CLI 자식 프로세스를 실행하므로, 같은 계정 인증을 이용해도 **동일 대화 세션 재사용과는 다르다.** CLI별 지원하지 않는 기능은 우회 성공으로 처리하지 않는다.

### 3.1 CLI LLM Adapter 설계

기존 LangChain 모델 계약을 최대한 유지하는 어댑터를 추가한다.

- `BaseChatModel` 계열 호환 (`invoke`, `ainvoke`, `bind_tools` 등 **실제 호출 지점에서 요구하는 범위**)
- 역할별 메시지(system/user/assistant/tool), 이미지·텍스트 첨부, 구조화 출력(JSON/schema) 변환
- 프롬프트 및 도구 스키마를 각 CLI가 받아들일 수 있는 입력으로 변환
- CLI 표준출력과 표준에러 분리, JSON 응답 검증, 부분 출력/실패 감지
- 비동기 실행, 타임아웃, 취소, 프로세스 종료, 요청 직렬화, 재시도/백오프
- 에이전트별 호출 상태/대화 문맥 유지: 기존 메시지 이력 전달 또는 CLI가 공식 지원하는 세션 이어받기 사용
- 공급자별 추론 결과를 **기존 에이전트가 기대하는 메시지·tool call·usage 메타데이터**로 역변환
- API 키가 아닌 **설치된 CLI의 공식 로그인 상태** 검증. 내부 토큰 추출·비공식 인증 우회 금지
- 텍스트/이미지/도구 호출/JSON/긴 대화/대용량 입력 등 지원 기능을 CLI별 capability matrix로 관리

**중요:** “모든 에이전트 유지”는 인터페이스와 동작 보존 목표다. CLI가 구조화 출력·이미지·도구 호출을 동등하게 지원하지 않는다면 **기능 차이를 검출하고 명시**해야 한다. 모델별 출력 차이가 있어 원본과 완전 동일한 결과는 보장할 수 없다.

### 3.2 native Gemini 호출 경로

일부 Explorer·영상 분석 기능은 `get_llm()` 대신 Google GenAI SDK를 직접 사용한다. 이런 부분도 제거 대상 **에이전트 자체가 아니라, 추론 호출 경계**다.

1. 직접 SDK 호출을 코드 검색·호출 그래프로 전수 식별한다.
2. 공통 CLI 모델 어댑터 또는 호환 추론 포트로 호출을 이동한다.
3. 기존 프롬프트, 입력 이미지, 도구 선언, 후처리, 복구 알고리즘을 보존한다.
4. CLI별 한계(영상 입력, native tool 호출, 캐싱 등)는 별도 지원 여부와 회귀 테스트로 판단한다.

## 4. 단계별 작업 계획 (SOL 6.1 Medium 실행 기준)

### P0. 원본 스냅샷과 호환성 PoC — 구현 전 **필수 통과 관문**

1. `google/artemis` 원본을 별도 디렉터리에 복제하고 기준 SHA 기록.
2. 목표 저장소 `callisto_auto`를 별도로 복제. 원본 `.git` 이력은 합치지 않음.
3. CLI 설치 및 공식 인증 상태, 비대화형 호출 가능 여부를 확인한다.
4. 최소 입력으로 **텍스트 추론, 이미지 입력, JSON schema, tool calling, 여러 턴 컨텍스트, 취소/timeout**을 CLI별 실험한다.
5. 특히 Codex CLI/Claude Code/Gemini CLI 중 **실제로 작동하는 첫 공급자 1개**를 선정한다.
6. 결과를 `docs/cli-capability-matrix.md`에 기록하고 불지원 항목/해결 전략을 명시한다.

**통과 기준:** 별도 AI API 키 없이 인증된 CLI로 ARTEMIS가 요구하는 핵심 응답 계약을 재현할 수 있거나, 핵심 기능을 유지할 수 있는 검증된 호환 방법이 있어야 한다. 충족하지 못하면 Pro 내부 로직을 뜯어고치지 않고 중단·보고한다.

### P1. 필요한 ARTEMIS 소스만 이관

1. Pro 그래프 및 모든 관련 에이전트, 모델 호출 인터페이스, ADB/Helper, 설정·Trace 및 종속 코드 분류.
2. **전체 원본은 로컬에 보관**, 목표 Git에는 실제 필요한 소스·리소스·테스트·라이선스만 추가.
3. `.env`, API 키, 세션·인증정보, 사용자 캡처·로그, 빌드 산출물 제외.
4. `LICENSE`, `NOTICE` 및 포함된 제3자 고지 보존.
5. 기존 테스트를 가능한 범위에서 실행해 **이관 기준선(baseline)** 확보.

**완료 산출물:** `docs/upstream-baseline.md`, 보존/제거 대상 목록, 최소 설치 성공.

### P2. CLI Adapter 도입 (중심 작업)

1. 기존 `artemis/services/llm.py`, `artemis/llm/router.py` 및 에이전트 호출점을 매핑.
2. 기존 model interface에 **CLI Adapter**를 새 공급자 경로로 삽입.
3. 먼저 텍스트 + structured JSON + tool call 반환을 구현하고 fake CLI 모킹 테스트 작성.
4. 이미지·멀티모달, native Gemini 경로, 세션/동시성 요구를 차례로 호환.
5. 기존 에이전트 내 계획/판단/검증 루틴 및 프롬프트는 바꾸지 않음.
6. 이전 API 직접 호출 지점이 남아 있지 않도록 정적 탐색 + 실행 시 검증.

**완료 산출물:** `callisto/llm_adapter/` (실제 저장 위치는 의존성에 맞게 조정), 어댑터 계약 테스트, CLI별 설정.

### P3. 웹·외부 MCP·Flash 실행 프로필 정리

1. `run`을 **서버 자동 실행 없는 로컬 standalone** 방식으로 변경.
2. 브라우저 UI, 관리자 웹 API, 대시보드, HTTP Daemon, 웹 전용 패키징 루틴 제거.
3. 외부 MCP 서버 및 진입점 제거. 내부 액션 세션은 유지.
4. Flash **실행 경로** 제거하고 Pro 기본·단일 실행 프로필로 제한.
5. Pro 기능에서 사용하는 공통 모듈과 Explorer tier를 오삭제하지 않도록 import/테스트 검증.
6. `setup.py`의 프런트엔드 빌드 요구 및 `pyproject.toml`의 불필요한 직접 의존성 정리.

**완료 기준:** 웹 UI/Daemon/MCP 서버를 설치하거나 시작하지 않아도 Pro 테스트가 정상 동작한다.

### P4. Callisto CLI·Skill 연결

1. `callisto doctor`, `callisto run`, `callisto trace` 등 **기존 CLI 명령을 최대한 재사용**한다.
2. `callisto run "설정 앱에서 배터리 화면 확인"` 호출 시 기존 Pro 그래프를 실행한다.
3. Skill에는 설치 확인, CLI 호출, 결과 수집, 오류 보고 절차만 넣는다. **에이전트 추론 로직을 Skill로 이전하지 않는다.**
4. 명령 실행 결과는 사람이 읽는 로그와 JSON/Trace 파일로 제공한다.
5. 호스트 AI CLI가 Callisto를 호출하고, Callisto 내부 에이전트는 CLI Adapter를 통해 추론한다.

**완료 산출물:** `skills/callisto/SKILL.md`, 사용 설명서, 실행 예제.

### P5. 기존 기능 동등성 검증 및 Git 반영

- 환경: Windows/Linux 설치, 여러 기기 감지, 실제 기기 또는 에뮬레이터 연결
- 실행: Pro 그래프, 모든 핵심 에이전트·체크포인트, 동작 복구, 취소
- 인지: 스크린샷, UI XML, 텍스트 입력, 제스처, 이미지 기반 판단
- 추론: CLI 인증, 텍스트/이미지/JSON/tool calls, 실패 및 재시도
- 결과: 기존 Trace, 성공·실패 판정, 결과 리포트
- 제거: 직접 AI API 호출·웹 UI·외부 MCP 서버·Flash 실행 프로필이 없는지 확인
- 보안: API 키·CLI 로그인 토큰·기기 개인정보·Trace 미유출
- 회귀: 원본 Pro 기반 테스트와 Callisto 테스트의 비교; 기능별 차이 기록

모든 필수 항목의 증거(테스트 결과·로그·지원 매트릭스)를 남기고 통과한 변경만 `main`에 반영한다.

## 5. 기술적 위험과 의사결정 기준

| 위험 | 대응 |
|---|---|
| CLI 비대화형 모델 호출이 제한적 | P0에서 검증하고 지원 CLI부터 우선 연결; 기능을 임의 제거하지 않음 |
| 같은 호스트 CLI 세션에 직접 접근 불가 | 별도 인증된 CLI subprocess와 기존 에이전트 메시지 문맥 전달; 동일 세션이라고 주장하지 않음 |
| JSON / tool calling 결과 불일치 | 기존 응답 스키마 검증, 재요청/오류 반환, 회귀 테스트 |
| Gemini native 특화 기능이 다른 CLI에서 미지원 | 경계 어댑터·capability gate로 분리, 대체 경로가 검증되지 않으면 미지원 표시 |
| 빈번한 CLI 프로세스 실행 비용·지연 | CLI 세션 재사용 가능 여부 확인, 캐시·요청 예산·타임아웃 최적화. 기존 에이전트 알고리즘은 유지 |
| 웹 코드 제거가 로컬 런타임을 손상 | standalone 기준선 확보 후 의존성 순서대로 제거 |
| Pro와 Flash가 공유하는 코드 삭제 | 실행 프로필과 Explorer 탐색 tier 구분, Pro 회귀 테스트 선행 |
| 외부 서버 제거를 위해 내부 MCP까지 삭제 | 내부 in-process 액션 전달은 보존, 별도 후속 검토 |
| 인증·개인정보 유출 | CLI 공식 인증 사용, subprocess 인자 안전하게 구성, 민감 로그 마스킹, 파일 권한 제한 |

## 6. 구현·검증 작업 규칙

1. **원본 기능 보존 최우선:** 에이전트 코드 수정은 새 CLI Adapter 호출에 꼭 필요한 최소 범위만 허용한다.
2. **추론 경계 집중:** 로직 재작성·프롬프트 재설계는 하지 않는다. 동일 기능을 검증한 경우에만 대체 경로를 연결한다.
3. **증거 기반 개발:** 미테스트 기능을 정상이라고 보고하지 않는다. CLI 옵션·모델·인증·멀티모달 지원은 설치된 버전에서 확인한다.
4. **최소 변경:** 무분별한 rename/대량 정리/파일 이동/포맷 변경을 금지한다.
5. **단계별 커밋:** 작업 단계마다 회귀 결과를 확인한다. `main` 직접 수정 전 별도 작업 브랜치 사용을 권장한다.
6. **권한과 자격증명:** 개인 인증 토큰을 읽어 복사하거나 API 요청으로 전환해 우회하지 않는다. 인증은 사용 중인 CLI가 자체 처리한다.
7. **라이선스:** ARTEMIS Apache-2.0과 각 제3자 라이선스·NOTICE를 유지한다.

### 권장 커밋 순서

```text
chore: import selected ARTEMIS source and license notices
 test: establish Pro regression baseline
 feat: add authenticated AI CLI model adapter
 refactor: route native AI calls through CLI adapter
 refactor: remove web UI daemon and external MCP entrypoints
 refactor: restrict execution to Pro profile
 feat: add Callisto CLI and AI CLI skill
 test: verify Android automation and provider parity
 docs: finalize setup support matrix and migration report
```

## 7. SOL 6.1 Medium 전달용 작업 지시

> Callisto 작업을 시작하라. 원본 `https://github.com/google/artemis`의 기준 커밋을 확인해 필요한 소스를 `https://github.com/cjftya/callisto_auto.git`에 선별 이관한다. **ARTEMIS의 Pro 그래프 및 Planner/Operator/Explorer/Validator/Checker 등 내부 에이전트의 동작·프롬프트·상태 관리·복구 로직은 변경하지 않는다.** 기존 AI API 호출만 인증된 AI CLI를 호출하는 호환 어댑터로 교체한다. native Gemini 등 우회 호출 경로도 전수 조사한다. 웹 UI, HTTP Daemon, 외부 MCP 서버, Flash 실행 프로필은 제거하되 Pro의 내부 in-process 액션 세션과 Explorer 탐색 tier 등 필요한 공통 구현은 보존한다. 먼저 CLI 비대화형 텍스트/이미지/JSON/tool calling PoC를 통과시키고 나서 실제 이관·연결 작업을 진행한다. 단계별 테스트를 남기고, 기능 동등성이 확인된 변경만 `main`으로 반영한다. 지원하지 않는 CLI 기능은 숨기거나 임의로 동작을 축소하지 말고 보고한다.

## 8. 최종 완료 조건 (Definition of Done)

- [ ] 필요한 ARTEMIS 소스·라이선스가 Callisto에 선별 이관됨
- [ ] 기존 Pro 에이전트와 실행 그래프 및 관련 검증 기능이 보존됨
- [ ] **모든 AI 추론 호출이 CLI Adapter를 통과**하고 직접 API 키가 필요 없음
- [ ] 각 지원 AI CLI의 텍스트·이미지·JSON·도구 호출 호환성이 검증됨
- [ ] 사용자용 웹 UI, 웹 Daemon, 외부 MCP 서버 없이 동작함
- [ ] Flash 실행 프로필은 제거, Pro 내부 공유 코드는 유지됨
- [ ] Android 실제 기기 또는 에뮬레이터에서 자연어 자동 테스트가 실행됨
- [ ] 실패·타임아웃·취소·기기 연결 오류가 적절히 보고됨
- [ ] 기존 Trace/리포트/체크포인트 등 핵심 결과물이 보존됨
- [ ] Windows/Linux 지원 범위와 설치·실행 방법이 문서화됨
- [ ] 기능 회귀·보안·의존성 검증 후 `main` 반영됨

---

### 검증에 사용한 원본 경로

- [소스 트리](https://github.com/google/artemis/tree/351ca8422f7b5b54e80a9c1ce03a222e02415b6b)
- [CLI 실행](https://github.com/google/artemis/blob/351ca8422f7b5b54e80a9c1ce03a222e02415b6b/artemis/interfaces/cli/commands/run.py)
- [LLM 라우팅](https://github.com/google/artemis/blob/351ca8422f7b5b54e80a9c1ce03a222e02415b6b/artemis/llm/router.py)
- [내부 액션 세션](https://github.com/google/artemis/blob/351ca8422f7b5b54e80a9c1ce03a222e02415b6b/artemis/mcp/action_session.py)
- [패키징](https://github.com/google/artemis/blob/351ca8422f7b5b54e80a9c1ce03a222e02415b6b/setup.py)

**문서 범위:** 실행 계획서. 본 문서 작성 시점에 Callisto 대상 저장소에는 코드 변경이나 커밋을 수행하지 않았다.
