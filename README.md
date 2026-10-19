# Callisto

Google ARTEMIS의 Pro 에이전트를 보존하면서 직접 AI API 호출을 인증된 AI CLI로 전환하는 프로젝트예요.

**현재 상태: P0 차단. Android 자동 테스트 엔진과 CLI 어댑터는 아직 이관·구현하지 않았어요.**
2026-10-19 환경에서 Codex는 로그인 상태를 표시했지만 실제 실행에서는 인증 관련
401 경고와 응답 시간 초과가 발생했어요. 로그인 상태 표시를 추론 성공으로 간주하지 않아요.

## 준비 상태 확인

Python 3.10 이상에서 추가 패키지 없이 실행할 수 있어요.

```sh
python tools/probe_cli.py --codex codex --timeout 45
python -m unittest discover -s tests -v
```

CLI가 PATH에 없다면 `--codex`에 실행 파일의 절대 경로를 전달하세요.
공식 `codex login`으로 로그인한 환경에서 실행해야 해요.
실제 모델 호출은 계정 사용량을 소비할 수 있어요.
점검 도구는 자격증명을 읽거나 복사하지 않으며 원본 CLI 로그를 저장하지 않아요.

이 도구는 **텍스트 관문만** 검사해요. 종료 코드 0도 전체 P0 통과를 뜻하지 않아요.
이미지, JSON schema, 에이전트 도구 호출 반환, 여러 턴 문맥, 취소 검증은 별도로 필요해요.
현재 `callisto run/doctor/trace` 명령이나 Android 자동화 실행 기능은 제공하지 않아요.

- [CLI 지원 현황과 차단 원인](docs/cli-capability-matrix.md)
- [원본 기준선과 이관 경계](docs/upstream-baseline.md)
- [후속 작업과 master 반영 범위](docs/migration-status.md)
