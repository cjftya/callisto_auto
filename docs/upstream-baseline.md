# ARTEMIS 원본 기준선

- 원본: https://github.com/google/artemis
- 검증된 HEAD: `351ca8422f7b5b54e80a9c1ce03a222e02415b6b`
- 대상 저장소 초기 커밋: `3aa3ccb` (`main`, README만 존재)
- 원본은 별도 디렉터리에 복제했고 Git 이력을 대상 저장소에 합치지 않았어요.
- 추적 소스 817개, `tests/` 파일 245개를 확인했어요.
- P0 차단으로 원본 코드 이관, 의존성 설치 및 Pro 기준선 테스트는 수행하지 않았어요.
- Android ADB 실행 파일은 PATH에서 발견되지 않았으며 기기 테스트를 수행하지 않았어요.

## 보존 대상

`artemis/graph/`, `artemis/agents/`, `artemis/services/llm.py`, 상태와 체크포인트,
ADB 및 Accessibility Helper, Trace, 내부 `artemis/mcp/action_session.py`,
`third_party/mobile_use/`의 런타임 의존 코드와 라이선스/NOTICE예요.
Explorer의 `flash` tier는 Flash 실행 프로필과 구분해 보존해야 해요.

## 확인된 직접 AI 통신 경계

| 경로 | 확인된 통신 |
|---|---|
| `artemis/llm/router.py` | Google/OpenAI/Anthropic 등 LangChain 공급자 생성 |
| `artemis/sdk/agent.py:156` | GenAI client 생성과 사전 연결 |
| `artemis/agents/explorer/explorer.py:149` | GenAI client 생성 |
| `artemis/agents/explorer/native_runner.py` | Files upload, caches create/delete, generate_content |
| `artemis/agents/video_analyzer/video_analyzer.py:434` | GenAI client 생성 |
| `artemis/agents/video_analyzer/native_coordinator.py:328` | generate_content_stream |
| `artemis/agents/video_analyzer/chunk_conversation.py:221` | generate_content_stream |
| `artemis/agents/video_analyzer/audio_native.py:465` | generate_content |
| `artemis/agents/video_analyzer/gemini_files.py` | Files upload/get |
| `artemis/agents/video_analyzer/chunk_agentic.py` | Interactions create/get |

이는 초기 정적 조사예요. 도달 가능한 모든 호출에 대한 감사 완료를 뜻하지 않아요.
Explorer의 기존 `_detect_native_engine()`은 Gemini 모델과 인증/공유 client 유무에 따라
native 경로를 선택하며, 그 외에는 universal 엔진을 사용해요.
기존 universal 경로의 동등성 확인 없이 native 기능을 삭제하면 안 돼요.

## 정리 예정 경계

- `run.py`: 기본 daemon 분기 대신 기존 standalone 경로 사용.
- 외부 `mcp_server/`, `apps/showcase_ui/`, `apps/admin_console/`, HTTP daemon 제거.
- Flash 실행 프로필만 제거하고 Pro 그래프 유지.
- `setup.py`의 UI 빌드 요구 및 `pyproject.toml`의 직접 AI/웹 의존성 감사.
- 원본 프롬프트와 판단·복구 알고리즘은 유지.

현 단계에서 위 제거·변경은 수행하지 않았어요.
