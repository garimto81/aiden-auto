---
name: reset-breaker
description: Circuit Breaker 상태를 수동으로 CLOSED 로 리셋합니다. 24h cooldown 또는 자동 HALF_OPEN 이전에 강제 회복이 필요할 때 사용. /reset-breaker 또는 평문 "circuit breaker 리셋" 으로 호출.
---

# /reset-breaker — Circuit Breaker 수동 리셋

aiden-auto 의 Circuit Breaker (`state/circuit-breaker.json`) 를 안전하게 CLOSED 상태로 강제 리셋합니다.

## 언제 사용

- iteration-runner 가 PDCA 루프 중 OPEN 상태에 갇혔고, 24h cooldown 을 기다리지 못할 때
- 외부 의존성 일시 장애 해소 직후, 즉시 재시도하고 싶을 때
- 개발/디버깅 중 실패 카운터를 깨끗하게 초기화하고 싶을 때

## 사용법

```bash
/reset-breaker
```

옵션 없음. 단일 명령으로 atomic 리셋 수행.

## 동작 (v28.3 FR-005)

```
1. plugins/aiden-auto/scripts/reset_breaker.py 호출
2. state/circuit-breaker.json 을 atomic write 로 다음 값으로 덮어쓰기:
   { "state": "CLOSED", "failures": 0, "last_failure": 0, "backoff": 1 }
3. 이전 상태와 변경 사항을 stdout 으로 출력
4. exit code 0 = 성공 / 1 = 파일 권한 등 실패
```

## 실행

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/reset_breaker.py"
```

## 안전 장치

- `state/` 디렉토리는 git 추적 금지 (Rule 19) — 리셋 결과 commit 안 됨
- atomic write (unique tmp + os.replace + retry) — race 없음
- 이전 state 가 무효 JSON 이어도 default 초기값으로 덮어쓰기 안전

## Troubleshooting Guide (block 메시지 보강 — v28.3 FR-005)

Circuit Breaker block 발생 시 화면에 표시되는 메시지:

```
Circuit breaker OPEN (backoff 4s)

원인: 동일 실패가 3회 누적되어 자동 차단됨.
해결책:
  1. 일시 장애가 해소되었다면: /reset-breaker
  2. 24시간 후 자동 HALF_OPEN 전환 대기
  3. 근본 원인이 미해결이면: 실패 로그 확인 후 코드 수정

상세: plugins/aiden-auto/commands/reset-breaker.md
```

## 관련

- `hooks/circuit_breaker.py` — Circuit Breaker 본체
- `hooks/session_init.py:725-735` — 24h HALF_OPEN 자동 전환
- `state/circuit-breaker.json` — 상태 파일 (atomic 갱신)
- Rule 17 `17-loop-circuit-breaker.md` — 카운터 상한 정책
