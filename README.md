# aiden-auto v28.1

**Index Router** — Intent 분석 후 chapter 1개만 lazy load 하는 최소 진입점 + 외부 harness framework 자가개선 사이클.

## 5가지 핵심 원칙

1. 외부 harness framework 그대로 유지 (참조만, 복사 안 함)
2. 매일 update 자동 critic → 자가개선 (`harness-watcher/critic/applier`)
3. SKILL.md 최소 진입점 (≤120줄, lazy load only)
4. Intent → Chapter 라우팅
5. 스킬/커맨드/워크플로우 = 방대 (슈퍼앱)

## 설치

```bash
# Claude Code marketplace
/plugin install garimto81/aiden-auto

# 또는 로컬 개발
git clone https://github.com/garimto81/aiden-auto ~/.claude/plugins/aiden-auto
```

## 빠른 시작

작업을 평문으로 말하기만 하면 됩니다. `/auto` 입력 불필요.

```
"로그인 API 만들어줘"        → 자동으로 code chapter 실행
"이 PRD 분석해줘"            → 자동으로 doc chapter 실행
"테스트 깨진 거 고쳐줘"        → 자동으로 qa chapter 실행
"기능 개선 반복해줘"           → 자동으로 iteration chapter 실행
```

## 핵심 특징

- **사용자 진입점 최소화**: Rule 16 자동 트리거. 명시 호출 불필요
- **자율 이터레이션 최대화**: Iteration V10.0 (13 specialist agents)
- **Multi-perspective 검증**: architect + security + test + verifier 동시
- **범용 적용**: Windows/Mac/Linux + Python/JS/Rust/Monorepo
- **Circuit Breaker**: 4-카운터 hard limit으로 무한 루프 방지

## 구조 (실측 2026-05-11)

```
aiden-auto/                              (162 elements)
├── skills/        22 (auto 진입점 ≤120줄 + chapter 22)
├── agents/        34 (iteration 13 + verification 4 + creative 2 +
│                      meta 5 [+harness-watcher/critic/applier 신규] +
│                      core/domain 10)
├── hooks/         27 (PreToolUse Agent matcher 비활성 — v28.1에서
│                      옛 Agent Teams 강제 패턴 해소)
├── rules/          8 (rule 16 auto-trigger + rule 17 Circuit Breaker + 6)
├── references/    38 (chapter 6 + phase 5 + v28.1 신규 3:
│                      plan-design-gate / ml-assist / external-harness-registry)
├── commands/      20
├── lib/           13 (calendar/figma/gmail/jira/slack/confluence 등 +
│                      advisor/ai_auth/workflow_critic 고유)
└── config/         3 (platform/profile/eco)
```

## 라이선스

MIT

## 출처

- C:\claude v18.0 (hooks, commands, lib, embedded-critic)
- aiden-auto v27.2 (chapter routing, iteration V10.0, verification specialists)
