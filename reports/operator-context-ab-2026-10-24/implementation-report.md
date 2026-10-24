# Callisto Operator A+B 구현·오프라인 검증 보고

작성일: 2026-10-24 (한국 시간)

## 1. 결론과 적용 상태

A1 계측, A2 기존 Capsule 임계값 비교, B1 Context IR/Shadow, B2 Evidence/Pin 및 ready-only 송신 view를 구현했어요. **운영 기본값은 `off`이며 실제 토큰 절감·Android 자동화 정확도는 검증하지 않았어요.** C의 CLI 세션 재사용은 제외했어요.

- 기준 `main`: `cf4b4122dd1244b2e96b268feb2b652e427a8396` — GitHub에서 최신 main과 일치하는 것을 확인했어요.
- 작업 브랜치: `work/operator-context-ab-20261024`.
- 주요 구현 커밋: A1 `f40649d`, A2 `969052b`, B1 `6ccf42d`, B2 `e2a8655`. 후속 문서·호스트 테스트 조정은 이 브랜치의 후속 검증 커밋에 포함돼요.
- `main`에는 병합하거나 push하지 않았어요. 검토 대상은 **로컬 작업 브랜치**예요. 작업 브랜치의 원격 push는 자동 승인 검토가 사용자의 push 금지 지시와 원격 대상 신뢰 확인 부족을 이유로 차단했어요. 우회하거나 원격에 반영하지 않았어요.
- 원본 core 32개 + engine 23개, 두 manifest 모두 변경하지 않았어요.
- 기존 로컬 보고서의 단일 text wrapper 축소와 `test_operator_input.py`는 기준 main에 없었어요. 이번에도 그 변경이 이미 적용됐다고 전제하거나 절감 효과에 합산하지 않았어요.
- 기존 이미지 변환·동일 첨부 dedup·bounded 변환 캐시를 새 최적화로 집계하지 않았어요. 추가 crop/rotation/해상도 하향은 없어요.

## 2. 구현 완료 기능과 미완료 범위

| 단계 | 구현한 기능 | 제한·미완료 |
| --- | --- | --- |
| A1 | raw usage 보존, 공급자별 logical/uncached/cache-read/cache-write/output/thought 정규화, scope/version, null·부분합, 본문/stdin/이미지/영역 바이트, run/agent invocation/observation/attempt/loop, lock 대기·프로세스 시간, summary 출처 | 설치된 공식 CLI 버전의 실제 출력 fixture는 미수집. plan bounce/validation/retry의 세부 원인은 확정하지 못하면 unknown이에요. |
| A2 | start 0.35/0.25/0.0, inner-loop 1/2/4/8, 4/16 관측, ready/pending/failed/delayed 비교; 실제 capsule prompt 렌더링과 scripted Python 자식 전송 | meter 22,000은 임계값 자극용 합성값이에요. 가짜 응답은 실제 Pro의 판단 품질이나 recall 필요성을 증명하지 않아요. |
| B1 | 불변 Context IR, 순서·tool ID/status·미완료 pair 계측, read-only 후보 view, 실제 전송 동일성을 확인한 Shadow | 의미 요약의 정확성은 기계적 coverage 검사만으로 증명할 수 없어요. |
| B2 | asset/evidence 분리, 역할·출처·geometry·summary 상태, 명시적 pin/release, 최근 floor·ready·coverage·연속 prefix·바이트 이득 검사, ready-only opt-in, off 복귀 | **기존 Pro의 incident/판단 완료를 pin 해제 이벤트로 자동 연결하는 작업은 미완료예요.** 현재는 명시적 hook만 있고, 자동 해제 추측은 하지 않아요. |
| 최종 | 전체 회귀, lint, pip check, frontend 없는 wheel, 독립 설치/Pro import/CLI help/Skill/Helper bundle 검사 | 실제 Windows 호스트, 공식 AI CLI, Android 기기 및 실제 품질 수용은 실행하지 않았어요. |

A1은 내용 없는 계측과 usage 해석을 추가해요. B의 입력 변경은 `ready_only`를 명시적으로 선택한 경우에만 적용돼요. 두 기본 config는 모두 `context_policy: "off"`이며 start 0.35, budget 80,000, soft/hard 0.7/0.9, 최근 raw 5 turns, image depth 3/3, grace 3을 유지했어요.

## 3. 변경 파일과 설계 결정

| 파일·영역 | 변경 목적 |
| --- | --- |
| `callisto/llm_adapter/usage_normalization.py`, `providers.py`, `model.py`, `callisto/usage.py` | 원본 counter와 정규화 의미·scope를 분리하고 합계의 이중 계산과 unknown→0 변환을 방지해요. |
| `callisto/llm_adapter/prompt_metrics.py`, `context_ir.py`, `codec.py` | S/D/H/O/R/unknown 계측, 불변 IR, 구조적 status, 이미지 geometry 및 내용 hash를 저장하지 않는 재노출 횟수를 제공해요. |
| `artemis/services/llm.py`, 공유 visual summarizer·capsule lens | 실행 출처와 논리 호출 index를 전달해요. 공용 raw model 캐시에 실행 세션을 저장하지 않아요. |
| `callisto/context_policy.py`, `artemis/memory/transcript.py`, `chunking.py` | 기존 ledger를 기준으로 삼고, 완료된 ready prefix를 **송신 view에서만** 교체해요. canonical active span과 원본 증거는 삭제하지 않아요. |
| `callisto/evidence.py`, 공유 `context_compressor.py`, `artemis/tools/tool_wrapper.py` | current/comparison/recalled/historical/overlay/unknown, step/tool-call 출처, explicit pin, summary 상태와 좌표계를 연결해요. |
| `artemis/config/agent.py`, 두 `artemis.jsonc` | off/shadow/ready_only schema와 기본 off를 추가해요. |
| `tools/compare_operator_context.py`, 새 회귀 4개 파일 | 동일 이력과 scripted 응답으로 구조·입력량을 비교해요. |
| `tests/conftest.py` | Work의 PID/procfs 불일치에서만 기존 제거 스크립트 실프로세스 검사를 skip해요. 일반 호스트·CI에서는 유지돼요. |
| 활성 문서 3개 | 사용 방법, 기본값, 미검증 범위, 명시적 pin 해제와 rollback을 설명해요. |

### Usage 의미

Codex cached input은 전체 input의 부분집합으로 처리해요. Claude는 input/cache-read/cache-write가 모두 있으면 합산하고 하나라도 누락되면 전체는 null이에요. `num_turns=1`을 확인하지 못한 Claude invocation 합계와 Gemini invocation 합계는 마지막 요청의 context 크기로 간주하지 않아요. Gemini는 기존에 지원하는 `models.*.tokens` 계약에서 모든 모델의 해당 필드가 확인될 때만 합산해요. 미지원 형태는 raw로 보존해요.

확인되지 않은 scope나 session cumulative counter는 run 정규화 합계에 더하지 않아요. C가 제외되었으므로 세션 차분 프로토콜도 추가하지 않았어요. 기존 `cli_usage`와 legacy 합계 key는 호환을 위해 남겼으며, 새 분석에는 `normalized_*`와 `known_normalized_*`를 사용해야 해요.

공식 의미 확인에 사용한 문서: [Claude prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [Gemini headless](https://geminicli.com/docs/cli/headless/), [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode). 문서 기반 counter 해석은 설치된 CLI의 실출력 검증을 대신하지 않아요.

### 보존과 rollback

- 현재 화면은 모든 stateless 요청에 실제 이미지로 남아요. 현재 loop를 semantic summary로 바꾸거나 tool 결과를 잘라내지 않아요.
- cost view는 가장 오래된 연속 ready prefix만 사용해요. pending 하나를 건너뛰지 않아요. source step ID/interval coverage, closed tool transactions, 최근 floor, 이미지/pin, 오류/Not executed, 크기 이득을 검사해요.
- 현재 ephemeral 안내가 있으면 incident 여부를 추측하지 않고 조기 압축을 보류해요. 이 보수적인 조건 때문에 실사용의 절감 폭은 작아질 수 있어요.
- 조회 이미지와 출처 미확인 이미지는 자동 age eviction을 하지 않아요. decision pin과 incident pin은 별도 이벤트로 해제해요. 자동 완료 이벤트 연결은 미완료라 장기 opt-in에서는 누적될 수 있어요.
- pin 32개/원본 32 MB, registry 4,096개를 넘으면 opt-in은 명시적인 오류를 내요. 증거를 조용히 버리거나 중요한 pin을 밀어내지 않아요. Shadow 한도 초과는 계측하고 기존 전송을 유지해요.
- opt-in에서 보호 증거가 기존 hard fold와 충돌하면 fold를 실행하지 않고 자원 오류로 중단해요. 기존 emergency ladder를 비용 압축으로 대신하지 않아요.
- off로 전환하면 새 비용 view를 해제해요. 기존 baseline scrub/hard 압축까지 역복원하는 기능은 아니며, 이미 그런 상태 변경이 발생했다면 기존 DataEngine/checkpoint에서 새 문맥을 시작해야 해요.
- `get_step_screenshot` source step과 원본 DataEngine/검색/재생 도구는 유지해요. 같은 bytes의 current/recalled도 서로 다른 evidence이며, 픽셀 한 점이 다른 이미지를 유사 해시로 합치지 않아요.

## 4. 단계별 검증 결과

실제 AI CLI·기기 없이 `CALLISTO_FORBID_LIVE_CLI=1`을 사용했어요.

| 단계 | 실행 결과 |
| --- | --- |
| 기준선 | adapter + transcript + chunking 127개 통과, manifest 55개 일치 |
| A1 | adapter/usage/image/service 등 125개, memory/operator 89개, summarizer 27개 통과 (suite 간 중복 포함) |
| A2 | 비교 회귀 5개 통과; 96개 조합에서 Python 가짜 CLI 3,600회와 현재 화면/현재 loop 증거 검사 수행 |
| B1 | 기존 관련 회귀 173개 + 새 IR/Shadow/보호조건 9개 통과 |
| B2 | 최종 evidence/memory/history 경계 회귀 210개 통과; 별도 순서·config 회귀도 통과 |
| 최종 전체 | **2,391 passed, 35 skipped, 8 deselected**, 기존 라이브러리 warning 89개 |
| 최종 비교 | 160개 A/B codec·ledger 조합; B shadow/ready-only의 loop 1/2/4/8에서 추가 Python 가짜 CLI 480회 |
| 정적·패키지 | ruff 통과, pip check 통과, frontend 없는 wheel 빌드 및 clean-venv 설치·Pro import·CLI help·Skill install/update/status·Helper APK/manifest 검증 통과 |
| 보존 | 두 manifest 원문 불변, 포함 소스 55/55 SHA-256 일치, 두 기본 config byte 일치 |

첫 전체 실행은 2,391 passed / 4 failed / 31 skipped였어요. 실패한 제거 스크립트 4개는 변경 전 main에서도 동일하게 재현됐고, Work의 `os.getpid()`와 `/proc/self` 값 불일치를 확인했어요. 기존 host-specific skip 규칙에 해당 테스트를 추가한 뒤 전체를 다시 실행했어요. 실제 프로세스 보호/삭제 코드는 변경하지 않았어요. 일반 Linux/Windows 호스트에서는 이 검사를 여전히 실행해야 해요.

Windows 경로·Unicode·launcher·취소/프로세스 계약 fixture는 전체 회귀에 포함돼요. 실제 Windows 머신에서 이번 브랜치를 실행한 결과나 원격 Windows CI 성공을 주장하지 않아요. 작업 브랜치 push만으로는 현재 main/PR 대상 workflow가 실행되지 않아요.

## 5. 입력 크기·이미지 비교

대표 조건: 16개 합성 관측, 관측당 inner-loop 4회, ready Capsule. context gate 입력 22,000은 **합성 stimulus**예요. 비교 중 최근 floor·이미지 depth·grace·soft/hard는 고정했어요.

| 모드 | Operator 본문 UTF-8 bytes 합계 | Capsule prompt 포함 입력 bytes 합계 | 이미지 첨부 | 이미지 전송 bytes | Capsule 요청 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 기존 정책, start 0.35 | 9,631,574 | 9,823,268 | 124 | 81,964 | 3 |
| A 실험, start 0.25 | 6,321,014 | 6,512,708 | 124 | 81,964 | 3 |
| A 극단 비교군, start 0.0 | 6,321,014 | 6,512,708 | 124 | 81,964 | 3 |
| B Shadow, start 0.35 | 9,631,574 | 9,823,268 | 124 | 81,964 | 3 |
| B Ready-only, start 0.35 | 6,345,638 | 6,537,332 | 124 | 81,964 | 3 |

Ready-only의 Operator 본문 감소는 **34.12%**, 렌더링된 Capsule prompt를 포함한 입력 바이트 감소는 **33.45%**예요. ready-only에는 ToolMessage status를 추가로 명시하므로 단순 start 후보보다 본문이 조금 커요. 이 결과를 토큰·요금 절감률로 해석하면 안 돼요.

짧은 4관측 작업은 capsule 조기 교체 이득이 없었어요. pending/failed Capsule은 조기 교체되지 않았고, delayed Capsule은 ready가 된 이후에만 차이가 났어요. pinned/unknown 이미지 보호는 오히려 첨부량을 늘릴 수 있어요. 이번 대표 fixture의 이미지 첨부가 줄지 않은 것도 그대로 보고해요.

- summary prompt는 실제 lens/codec으로 렌더링했지만 응답은 scripted capsule이에요. 요약 모델 추론 비용은 측정하지 않았어요.
- fixture의 recall·transport retry는 0이며, 실제 모델이 요약 후 조회/복구를 더 요구할 가능성은 포함하지 못해요. failed-summary fixture는 기존 재요청 cadence와 해당 prompt 크기를 계산해요.
- CLI harness·cache 재구축·요약 출력·추가 recall·다른 에이전트의 실제 비용을 포함한 순절감은 **미확인**이에요.
- 모든 actual-token 항목은 null이에요. PNG/JPEG/base64 바이트를 이미지 토큰으로 환산하지 않았어요.

## 6. 기능 보존 위험과 운영 활성화 전 수용 기준

1. 공급자별 설치 버전과 result scope를 고정하고 raw/normalized/cache counter를 실제 trace로 대조해야 해요. Claude/Gemini 다중 내부 요청을 마지막 문맥 크기로 오해하지 않는지 확인해야 해요.
2. 동일 시작 상태·시나리오에서 off/shadow/ready-only를 비교해야 해요. task 성공, assertion 판정, 잘못된 PASS, 복구 성공, 행동 수와 전체 지연의 허용 기준은 실행 전에 정해야 해요.
3. 작은 글씨·체크 표시·숫자 한 자리·회전/가로세로·비교 화면·명시적 과거 screenshot 조회·incident 지속/종료를 포함해야 해요.
4. **pin의 판단/incident 완료 이벤트 자동 연결을 검증한 뒤 운영 활성화를 검토해야 해요.** 지금은 자동 해제를 하지 않아 한도/압력 오류로 끝날 수 있어요. 이를 정상적인 무제한 운영 기능으로 보아서는 안 돼요.
5. 요약의 interval coverage가 모든 중요한 사실·사용자 제약의 보존을 보장하지는 않아요. 실제 모델의 capsule 해석·recall·복구 행동을 평가해야 해요.
6. checkpoint/cold start는 원본 DataEngine 복구 경로를 사용해요. 새 in-memory pin은 재시작 시 자동 재구성되지 않으므로 진행 중 incident의 증거를 다시 조회하고 보호해야 해요.
7. Windows 실제 호스트에서 프로세스 종료, 긴 stdin, Unicode 경로, 패키지 설치를 실행해야 해요. Work에서 생략된 실프로세스 테스트도 실행해야 해요.
8. 충분한 효과나 안전성을 확인하기 전에는 기본 `off`를 유지해요. 현재 결과만으로 모델·reasoning을 낮추거나 start gate·이미지 depth를 운영 기본값으로 바꾸지 않아요.

## 7. 재현과 검토 자료

```sh
CALLISTO_FORBID_LIVE_CLI=1 python -m pytest
python -m ruff check callisto tools tests/callisto
python -m pip check
CALLISTO_FORBID_LIVE_CLI=1 python tools/compare_operator_context.py --include-b --output comparison.json
python -m pip wheel --no-deps --no-build-isolation -w dist .
CALLISTO_FORBID_LIVE_CLI=1 python tools/verify_wheel.py dist/callisto_auto-0.1.2-py3-none-any.whl --require-helper
```

- [160개 codec/ledger 비교](comparison.json)
- [최종 B Python 가짜 CLI 480회 결과](fake-cli-replay.json)
- [패키지 검증 결과](wheel-report.json)
- [55개 소스 보존 검사](preservation.json)

가짜 CLI replay는 보존된 실제 Operator 전체 graph를 구동하는 실기기 수용 테스트가 아니에요. 실제 graph의 mixed request, plan gate, validation, recovery, history, checkpoint 계약은 기존 전체 회귀로 별도 확인했어요.

최종 검증 wheel SHA-256: `7e8c0f977a8282ec4a03499b9eb926ca467db73f47c04358b6dc163760ce47c5`.
