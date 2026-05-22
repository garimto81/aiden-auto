---
name: debate
description: "Gemma4가 Slack 채널의 gpt5/opus/gemini 앱에 동일 질문을 던지고 교차검토 후 합의 리포트를 작성하는 스킬 (ultimate-debate 5-Phase 구조). 메시지 전송은 반드시 User token 사용, 응답 대기는 최대 60초."
version: "2.1.0"
triggers:
  keywords:
    - "/debate"
    - "토론"
    - "debate"
    - "3앱 비교"
    - "멀티 AI"
    - "교차검토"
auto_trigger: false
options:
  "--rounds N": "최대 재토론 라운드 (기본 1)"
  "--threshold X": "합의 임계값 0.0~1.0 (기본 0.7)"

# CRITICAL 운영 규칙
runtime_rules:
  token_type: "USER_ONLY"
  token_rationale: "Bot token(xoxb-)으로 @mention 발행 시 대상 앱(gpt5/opus/gemini)이 응답하지 않음. 반드시 User token(xoxp-)으로 전송."
  response_wait_seconds: 60
  wait_rationale: "앱 응답 도착까지 충분한 시간 보장. 60초 초과 시 해당 앱 '(응답 없음)' 처리."
---

# /debate — Gemma4 Slack 앱 토론 스킬 v2.0

## 개요

`ultimate-debate` 5-Phase 구조 + 실제 Slack 앱(@멘션) 결합 버전.

```
Phase 1: 병렬 분석    → 3개 Slack 앱에 동시 @멘션 질문
Phase 2: 합의 체크    → Gemma4가 응답 비교 판정 (FULL/PARTIAL/NO_CONSENSUS)
Phase 3: 교차 검토    → 불일치 시 각 앱이 다른 앱 응답 리뷰
Phase 4: 재토론       → NO_CONSENSUS + --rounds 2+ 시 최종 입장 재확인
Phase 5: 최종 종합    → Gemma4 종합 리포트 + #claude-auto 게시
```

## 사용법

```
/debate "질문 또는 주제"
/debate "Python vs Go 성능 비교" --rounds 2
/debate "RAG와 Fine-tuning 중 어떤 게 나아?" --threshold 0.6
```

## 앱 정보 (claude-auto 채널)

| 앱명 | User ID | Bot ID | 특성 |
|------|---------|--------|------|
| gpt5 | U08C1E1ASQ6 | B08CWSVFDMW | 코딩·수학·논리 |
| opus | U0AHH5LFDA6 | B0AJBDPSM3J | 복잡한 분석·글쓰기 |
| gemini | U0AHH6G4VK4 | B0AJBEK2VQ8 | 최신 정보·검색 |

## 합의 프로토콜

| 상태 | 조건 | 다음 단계 |
|------|------|-----------|
| `FULL_CONSENSUS` | 일치율 ≥ threshold (기본 0.7) | Phase 5 바로 |
| `PARTIAL_CONSENSUS` | 0.5 ~ threshold | Phase 3 교차검토 |
| `NO_CONSENSUS` | < 0.5 | Phase 3+4 재토론 |

## 실행 워크플로우

### Phase 0: 입력 파싱

args에서 질문과 옵션 추출.
- args 비어있음 → AskUserQuestion으로 질문 입력 요청
- `--rounds N` 파싱 (기본: 1)
- `--threshold X` 파싱 (기본: 0.7)
- task_id 생성: `debate_{YYYYMMDD}_{질문앞6자}`

### Phase 1: 병렬 분석

**Step 1-a: Gemma4 앱 선택**

```bash
cd C:\claude && python3 vllm/scripts/gemma4_orchestrator.py select "<질문>"
```

반환 JSON에서 `apps`, `mention_messages` 추출.
선택된 앱 목록과 이유를 사용자에게 출력.

> 참고: 토론 특성상 Gemma4가 1개 앱만 선택하더라도 3개 앱 모두 사용.

**Step 1-b: User token으로 각 앱에 메시지 전송 (CRITICAL)**

⚠️ **반드시 User token 사용** — Bot token(xoxb-)으로 전송하면 대상 앱이 응답하지 않음 (Slack의 bot-to-bot 루프 방지 메커니즘).

**기본 경로 (권장): MCP `slack_send_message`**

MCP Slack 플러그인은 Browser OAuth로 인증되어 User token(xoxp-) 기반으로 동작한다. sender가 사용자 본인(U040EUZ6JRY)으로 찍히므로 대상 앱이 정상 응답.

```
tool: mcp__plugin_slack_slack__slack_send_message
args:
  channel_id: C0985UXQN6Q
  message: <mention_messages[앱명]>
```

**대체 경로: `lib.slack send --user`**

MCP 사용 불가 시 (연결 끊김 등) CLI fallback:
```bash
cd C:\claude && python -m lib.slack send C0985UXQN6Q "<mention_message>" --user --json
```

⚠️ `--user` 플래그 사용 시 slack_user_token.json에 `chat:write` 스코프 필요. 스코프 누락이면 `python -m lib.slack login --user`로 재인증 (Slack 앱 manifest에 user scope `chat:write`가 선언되어 있어야 함).

전송 완료 후 `ts`를 수집하여 sent_dict 구성:
```json
{"gpt5": "ts1", "opus": "ts2", "gemini": "ts3"}
```

**Step 1-c: 응답 수집**

```bash
cd C:\claude && python3 vllm/scripts/gemma4_orchestrator.py collect "<질문>" '<sent_dict_json>'
```

`responses` 딕셔너리 추출 (각 앱의 응답 텍스트).

**Step 1-d: Context 파일 저장** (선택)

`.claude/debates/{task_id}/TASK.md`와 `round_01/{앱명}.md` 저장.

### Phase 2: 합의 체크

```bash
cd C:\claude && python3 vllm/scripts/gemma4_orchestrator.py consensus "<질문>" '<responses_json>'
```

반환 JSON:
```json
{"consensus": "FULL_CONSENSUS", "score": 0.85, "reason": "설명"}
```

- `FULL_CONSENSUS` → Phase 5로 점프
- `PARTIAL_CONSENSUS` / `NO_CONSENSUS` → Phase 3 진행

사용자에게 합의 상태 출력:
```
[합의 판정] PARTIAL_CONSENSUS (score: 0.62)
→ 불일치 영역: <reason>
→ 교차 검토 진행...
```

### Phase 3: 교차 검토 (PARTIAL/NO_CONSENSUS 시만)

**Step 3-a: 교차검토 메시지 생성 + 전송**

```bash
cd C:\claude && python3 vllm/scripts/gemma4_orchestrator.py cross_review "<질문>" '<responses_json>'
```

반환: `cross_messages` (각 앱에 보낼 메시지, 다른 앱 응답 포함):
```json
{
  "gpt5": "<@U08C1E1ASQ6> 다른 AI들의 의견입니다: ...",
  "opus": "<@U0AHH5LFDA6> 다른 AI들의 의견입니다: ...",
  "gemini": "<@U0AHH6G4VK4> 다른 AI들의 의견입니다: ..."
}
```

**Step 3-b: User token으로 교차검토 메시지 전송**

Phase 1-b와 동일 경로 사용:
- 기본: MCP `mcp__plugin_slack_slack__slack_send_message`
- Fallback: `python -m lib.slack send C0985UXQN6Q "<cross_message>" --user --json`

반환 ts로 `sent_dict_cross` 구성.

**Step 3-c: 교차검토 응답 수집**

```bash
cd C:\claude && python3 vllm/scripts/gemma4_orchestrator.py collect "<질문> [교차검토]" '<sent_dict_cross_json>'
```

`cross_responses` 추출.

### Phase 4: 재토론 (NO_CONSENSUS + rounds ≥ 2 시만)

rounds 파라미터가 2 이상이고 NO_CONSENSUS 상태인 경우에만 실행.

교차검토 응답(`cross_responses`)을 다시 각 앱에 전달:

```bash
cd C:\claude && python3 vllm/scripts/gemma4_orchestrator.py cross_review "<질문> [최종입장]" '<cross_responses_json>'
```

`lib.slack send --user`로 전송 (Phase 1-b와 동일 패턴) → 응답 수집. `final_responses` 추출.

### Phase 5: 최종 종합

모든 라운드 데이터를 합쳐 Gemma4 종합:

```bash
cd C:\claude && python3 vllm/scripts/gemma4_orchestrator.py collect "<질문> [최종종합]" '<all_responses_json>'
```

`all_responses_json` 구성: round_01 + cross_responses + final_responses를 앱별로 합친 딕셔너리.

**터미널 출력:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 /debate 결과: <질문>
 합의 상태: PARTIAL_CONSENSUS (0.62)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Round 1 — 병렬 분석]
gpt5: <응답>
opus: <응답>
gemini: <응답>

[Round 2 — 교차 검토]
gpt5: <교차검토 응답>
opus: <교차검토 응답>
gemini: <교차검토 응답>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Gemma4 최종 종합
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<synthesis 내용>
```

**#claude-auto에 최종 리포트 게시 (MCP):**
```
channel_id: C0985UXQN6Q
message: <slack_message 필드>
```

### Phase 6: 완료 메시지

응답 시간, 합의 상태, 참여 앱 수, 라운드 수, Context 저장 경로를 요약하여 출력.

## 오류 처리

| 오류 | 처리 |
|------|------|
| Gemma4 미응답 | 전체 앱 사용 후 진행 |
| 앱 타임아웃 (120초) | "(응답 없음)" 표시, 있는 응답으로 합의 |
| 합의 판정 실패 | 기본 PARTIAL_CONSENSUS로 진행 |
| Cross-review MCP 실패 | 해당 앱 제외, 나머지로 계속 |
| Context 파일 쓰기 실패 | 메모리에서 계속, 파일 저장만 스킵 |

## 의존성

- `vllm/scripts/gemma4_orchestrator.py` — 앱선택, 수집, 종합, 합의판정, 교차검토
- `lib/slack/` — SlackClient (응답 수집)
- MCP: `mcp__plugin_slack_slack__slack_send_message` — 앱 호출
- Ollama (localhost:11434) — Gemma4 모델

## 알려진 이슈 (Known Issues)

### 🔴 [BLOCKER] 계정 변경으로 인한 Slack 인증 차단 (2026-04-26 진단)

**증상**: 스킬 실행 시 Phase 1-b (메시지 전송) 단계에서 차단되어 토론 진행 불가.

**원인**: Slack 워크스페이스 계정 변경 후 인증 자산이 새 계정에 맞게 재구성되지 않음.

**진단 결과** (작동 확인 시 발견):

| 항목 | 상태 | 영향 |
|------|:----:|------|
| `gemma4_orchestrator.py` | ✅ 정상 | — |
| Ollama Gemma4 (`localhost:11434`) | ✅ 정상 | — |
| `lib/slack/` 모듈 | ✅ 정상 | — |
| `python -m lib.slack status` 인증 | ⚠️ Bot only | `bot_user_id` 응답하지만 `scopes: []` 빈 배열 |
| User token (`slack_user_token.json`) | ❌ 부재 | CLI fallback 차단 |
| MCP Slack OAuth | ❌ 차단 | callback port 3118 점유 충돌 영구 |

**SKILL.md Phase 1-b 요구사항과 불일치**:
- Bot token(xoxb-)으로 전송하면 대상 앱(gpt5/opus/gemini)이 응답하지 않음 (Slack의 bot-to-bot 루프 방지)
- User token(xoxp-) 필수인데 두 경로 모두 차단

**해결 방향 (추후 개발 시 참고)**:

1. **User token 재인증 (1순위)**:
   ```bash
   python -m lib.slack login --user
   ```
   - 새 워크스페이스 계정으로 OAuth 진행 → `slack_user_token.json` 생성
   - Slack 앱 manifest에 user scope `chat:write` 선언 확인 필수

2. **MCP Slack OAuth 재시도**:
   - port 3118 점유 프로세스 해소 (재부팅 또는 점유 프로세스 식별)
   - `mcp__plugin_slack_slack__authenticate` 재호출
   - `/mcp` 슬래시 명령으로 수동 인증도 가능

3. **앱 정보 검증 (계정 변경 시 필수)**:
   - 새 워크스페이스에 gpt5/opus/gemini 3개 앱이 모두 설치되어 있는지 확인
   - 본 SKILL.md §앱 정보 테이블의 User ID/Bot ID가 새 워크스페이스 기준으로 맞는지 갱신
   - `claude-auto` 채널 ID(`C0985UXQN6Q`)가 새 워크스페이스에서 유효한지 확인

**작동 확인 절차 (재인증 후 검증용)**:

```bash
# 1. User token 인증 확인
python -m lib.slack status --json
# → "user_id": "U040EUZ6JRY"가 응답되어야 함 (또는 새 사용자 ID)

# 2. 채널 접근 확인
python -m lib.slack info C0985UXQN6Q --json

# 3. 앱 ID 검증 (새 워크스페이스에서 갱신된 ID 확인)
python -m lib.slack user U08C1E1ASQ6  # gpt5
python -m lib.slack user U0AHH5LFDA6  # opus
python -m lib.slack user U0AHH6G4VK4  # gemini

# 4. 가벼운 테스트 토론 (1라운드)
/debate "테스트: Python vs Go 어느 게 빠른가?"
```

**스킬 사용 전 사전 체크 권장**:

이 스킬을 호출하기 전에 위 진단 절차로 인증 상태를 먼저 확인할 것. 인증 차단 상태에서는 즉시 사용자에게 알려진 이슈를 알리고 재인증을 안내해야 함.

## 관련 파일

- 오케스트레이터: `C:\claude\vllm\scripts\gemma4_orchestrator.py`
- Context 저장: `C:\claude\.claude\debates\{task_id}\`
- Slack 모델: `C:\claude\lib\slack\models.py`
- PRD: `C:\claude\vllm\docs\00-prd\gemma4-orchestrator-v1.md`
- 통합 PRD: `C:\claude\docs\00-prd\prd-debate-integration.prd.md`
