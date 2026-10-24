# Operator 입력 비용 2차 최적화 — 구현 및 오프라인 검증

기준: `d9de35c1892bbf2d06e20ea89947e68c3283a622`, 2026-10-24 KST.
작업 브랜치: `feature/operator-evidence-cost-v2`. 기본값은 모두 off.
실제 모델 CLI/Android는 실행하지 않았으며 실제 토큰 절감·판정 정확도는 미검증이다.

## 구현 결과

- **P1:** 공유 `TranscriptLedger.commit_staged`에 안전한 조회 decision 종료를 연결했다. 원본 Operator/Validator 코드는 수정하지 않았다. 성공한 `get_step_screenshot` 호출/결과 ID, 후속 AI 판단, 닫힌 transaction, 정상 dispatch가 모두 있어야 해당 decision pin만 해제한다. 중간 오류/미완료/중단/timeout/비교/unknown은 유지한다. 실패 step은 incident pin을 추가한다.
- **P1 제한:** Validator의 incident CLOSED는 실행 채널 복구만 뜻하며 원래 의도 해결이 아니다. 원래 의도 완료의 구조화 신호가 없으므로 incident/comparison/overlay/unknown의 자동 종료를 추정하지 않는다. 기존 명시적 `release_evidence(event)`로 소유자가 확인해야 한다. 이 경우 장기 실행의 pin 한도에 도달할 수 있다. checkpoint 재개는 새로운 registry로 재등록·재조회하며 이전 해제를 신뢰하지 않는다.
- **P2:** 실제 codec 경계에서 역할별 첨부/바이트, 공유 참조, 필수 current 고유 자산, 추가 첨부, 동일 자산의 다른 evidence, 관측별 반복 첨부를 계측한다. 역할별 바이트는 처음 실제 첨부한 역할에 귀속하여 중복 합산하지 않는다. hash/prompt/pixels는 로그로 내보내지 않는다.
- **P2 후보:** `CALLISTO_OPERATOR_IMAGE_POLICY=shadow|ready_only`. 오래된 완료 turn의 unpinned historical, ready visual summary만 전송 사본에서 대체한다. 최소 최근 5 turns/현재 loop/오류/미완료/활성 안내/unknown/비역사 역할은 보존한다. shadow는 원래 입력을 유지한다. canonical ledger와 DataEngine의 원본은 이 view로 변경하지 않는다.
- **P3:** S/D/H/O/R/unknown 바이트와 재노출, history 종류를 분리했다. `CALLISTO_COMPACT_TEXT=1`은 단일 순수 text block만 문자열로 인코딩한다. 본문/순서/tool ID/name/status 및 추가 block metadata는 보존한다. 기존 main에 이 축소는 없었다. CLI 세션 재사용/캐시 적중 가정/모델 변경은 추가하지 않았다.
- **전체 비용:** usage의 mixed-provider 정규화 합계를 null로 하고 공급자별 합계를 추가했다. `compare_operator_acceptance.py`는 전체 agent와 Operator를 분리하고 정상 scope/동일 환경/수동 성공 판정이 있을 때만 uncached 감소율을 낸다. summary 호출과 실패 호출, output/cache-write도 함께 제시한다. 관찰 불가 recall/retry 수는 null이다.
- **P4:** 기존 입력 계약의 256개 결정적 비교, lifecycle/한도/오류/복구/unknown/회전 크기·작은 글씨·체크박스 보존 회귀, Python 가짜 자식 프로세스 전송 검증을 추가했다. Linux/Windows 기존 CI와 Helper 빌드를 유지하고 Linux에 256개 비교 artifact를 추가했다.

## 동일 baseline 재현: 16관측 × 4 inner-loop

| 구성 | Operator 본문 B | summary 포함 입력 B | 이미지 첨부 |
|---|---:|---:|---:|
| off | 9,631,574 | 9,823,268 | 124 |
| 기존 shadow | 9,631,574 | 9,823,268 | 124 |
| 기존 ready_only | 6,345,638 | 6,537,332 | 124 |
| ready_only + 이미지 shadow | 6,345,638 | 6,537,332 | 124 |
| ready_only + 이미지 opt-in | 6,345,638 | 6,537,332 | 124 |
| 위 구성 + compact text | 6,270,238 | 6,461,932 | 124 |

124개는 current 64 + historical 60이다. 남은 historical은 최근 보호 구간에 속하므로 신규 정책의 제거 후보는 0개다. 같은 stateless 요청에서 필요한 현재 화면은 유지한다. 이 fixture에서 이미지 감소를 주장하지 않는다. 별도 오래된 ready historical fixture에서는 후보/전송 사본 대체를 검증했다.

compact text는 기존 ready_only 대비 75,400 B, summary 포함 입력의 약 1.15%를 추가 감소시킨다. 원래 off 대비 약 34.22% 감소지만 대부분은 이전 ready_only 구현의 효과다. 숫자는 **누적 직렬화 바이트**이며 실제 토큰·가격·모델 행동 개선 수치가 아니다. 합성 이미지의 실제 전송은 모든 대표 구성에서 81,964 B로 같다. Provider별 stdin은 base64 등 전송 형식 차이를 따로 계측한다.

전체 256개는 4/16관측 × 1/2/4/8루프 × Ready/Pending/Failed/Delayed와 기존 압축 gate/신규 후보 조합이다. 요약 입력을 포함하며 actual_tokens는 모두 null이다. inner-loop에서 static/schema/기존 tool 반환을 반복 전송하는 비용은 여전히 남는다. 이를 제거하려고 현재 화면이나 도구 결과를 없애지 않았다.

## 검증과 한계

- 전체 회귀: **2,429 passed, 35 skipped, 8 deselected**. 이후 수용 비교의 복구 실패 제외와 실제 어댑터 환경변수 연결 회귀를 추가 검증했다. 최종 커밋의 CI 결과는 PR에서 확인한다.
- ruff, pip check, git diff --check 통과.
- 보호 manifest 두 개 그대로, 보호 소스 **55/55 SHA-256 일치**.
- frontend-free wheel build 및 clean venv 설치/Pro import/CLI help/Skill install·update·status 통과. canonical Helper APK 포함 확인. Linux/Windows Helper 재빌드·APK-bearing wheel 검증은 PR CI에 포함한다.
- 실제 Windows 호스트 프로세스/ADB/기기 설치·공식 CLI 버전 usage·시각 정확도는 PC P0/P5에서 검증해야 한다. 기본 pytest의 integration/e2e/android/manual 제외와 skip은 실제 수용 통과를 뜻하지 않는다.
- off/shadow 송신 계약은 유지하며 새 표현은 각각 명시 opt-in이다. 보호 소스/graph/prompt/model 설정/기존 capture 이미지 정책은 바꾸지 않았다.

## 이어서 할 일

`tests/fixtures/operator-cost-v2/`의 환경 기록·수동 판정·시나리오를 PC로 가져간다. 동일 provider/version/model 설정과 시작 상태에서 모드별 초기 3회씩 검토하되, 실제 유료 호출 전에 범위와 예상 호출 수 승인을 받는다. 원본 민감 이미지/본문은 업로드하지 않는다.

```sh
# 오프라인 재현
CALLISTO_FORBID_LIVE_CLI=1 python tools/compare_operator_context.py --include-b --include-v2 --no-child --output dist/operator-v2-comparison.json
# 수용 후 내용 없는 측정 보고서 비교
python tools/compare_operator_acceptance.py traces/off traces/ready_only --output acceptance-comparison.json
```

잘못된 PASS/필수 증거 누락/위험한 해제/복구 실패 시 opt-in을 끄고 원인을 재현한다. rollback: context_policy=off, CALLISTO_OPERATOR_IMAGE_POLICY=off, CALLISTO_COMPACT_TEXT unset/0. 원본 엔진이 이미 scrub/fold한 문맥은 DataEngine에서 새 실행으로 재구성해야 한다.

실기기 수용 전 기본 활성화와 main 병합은 하지 않는다. P0/P5/P6 최종 효과 판정은 보류다.
