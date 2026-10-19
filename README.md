# Callisto

Google ARTEMIS의 **기존 Pro 그래프·에이전트는 유지**하고, 모델 통신을 인증된 로컬 AI CLI로 연결하는 Android 자동 테스트 도구예요.

현재는 **구현 및 오프라인 검증 단계**예요. 실제 CLI 모델 호환성과 Android E2E는 사용자 PC에서 확인해야 해요. Work 내부에서 AI CLI를 실행하지 않으며, 그 실행 실패를 개발 중단 조건으로 사용하지 않아요.

## 로컬 PC 설치

Python 3.12 이상, Android Platform Tools(ADB), 인증된 Codex CLI가 필요해요.

Linux:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
callisto doctor --json
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
callisto doctor --json
```

`doctor`는 실행 파일과 설정만 검사해요. AI CLI를 실행하거나 인증·추론 성공을 주장하지 않아요.
AI CLI 로그인은 해당 CLI의 공식 절차로 사용자 PC에서 수행하세요. API 키나 로그인 토큰을 Callisto에 복사하지 않아요.

## 사용자 PC에서만 수행하는 검증과 실행

```sh
# 실제 모델 호출을 수행하므로 ChatGPT Work에서는 실행하지 마세요.
python tools/verify_local_cli.py --allow-live-cli
adb devices
callisto run "설정 앱에서 배터리 화면을 열고 배터리 항목이 표시되는지 확인" --device-serial SERIAL
callisto trace list
```

실행은 웹 UI·HTTP Daemon·외부 MCP 서버 없이 로컬 Pro 그래프로 진행돼요.
동일 호스트 AI의 현재 대화 세션을 재사용하는 방식은 아니며, 매 호출마다 기존 에이전트의 메시지 이력을 별도 CLI 프로세스로 전달해요.

`callisto run`은 세션 ID와 결과 JSON 경로를 출력해요. 원본 Trace, 체크포인트와 `run_outcome.json`을 함께 확인하세요.
종료 코드: 0 완료 / 1 실패 / 2 미확정·미실행 체크 존재 / 130 취소. 검증 항목이 없는 완료를 테스트 통과로 해석하지 마세요.

## 모델과 기능 범위

- Codex: 초기 구현 대상. 텍스트·이미지·JSON·도구 호출 반환·여러 턴 메시지 전달을 모의 테스트로 검증했어요. 기본 모델은 `gpt-6.1-sol`이에요.
- Claude Code: 텍스트 전송 실험 구현. `CALLISTO_AI_CLI=claude`와 `CALLISTO_MODEL`을 함께 지정해야 해요. 이미지 전송은 미구현이에요.
- Gemini CLI: 아직 미구현이에요. Google 원본의 native Files/Interactions/명시적 캐시·음성·검색 기능은 동등성이 확인되지 않았고, 호출 시 명시적으로 거부해요.
- 기존 Universal 영상 분석의 프레임/이미지 경로는 유지했어요. 실제 영상·음성 기능 전체가 동등하다고 주장하지 않아요.
- 선택적 OCR은 `CALLISTO_OCR=1`로 켜면 CLI 이미지 추론을 사용해 원래 텍스트/좌표 형식을 반환해요. 기존 Vision API 키로 자동 활성화하지 않아요. 실제 좌표 정확도 검증은 별도로 필요해요.

모델은 `CALLISTO_MODEL`, 실행 파일은 `CALLISTO_CODEX_EXECUTABLE`로 지정할 수 있어요. Codex 호출은 사용자 설정을 읽지 않고 저장된 공식 인증을 사용하며, 임시 디렉터리·read-only sandbox·JSON 출력으로 동작해요. 관리자가 강제한 정책은 우회하지 않아요.
Google 전용 모델(예: Robotics ER)의 공간 인지 정확도와 일반 CLI 모델의 결과가 같다고 보장하지 않아요.

## 오프라인 개발

```sh
python -m pytest
python -m pip wheel --no-deps --no-build-isolation -w dist .
```

자동 테스트는 실제 AI CLI 실행을 금지해요. 모의 응답과 가짜 Python 실행 파일만 사용해 계약, 취소와 프로세스 정리를 검증해요.
브라우저 UI, 관리자 콘솔, 외부 MCP, Flash 실행 전용 원본 테스트는 `tests/upstream_removed/`에 보관하고 기본 테스트에서 제외했어요. Pro가 공유하는 내부 MCP 액션 세션, Flash 폴더의 요약/압축 코드와 Explorer `flash` tier는 유지했어요.

- [CLI 지원 현황](docs/cli-capability-matrix.md)
- [전환 진행 상황](docs/migration-status.md)
- [원본 보존 기준](docs/upstream-baseline.md)
- [CLI Skill](skills/callisto/SKILL.md)
- [라이선스](LICENSE), [제3자 고지](third_party/mobile_use/NOTICE)
