# aiden-auto v28.0

Universal Adaptive Orchestrator — Claude Code 통합 슈퍼 플러그인.

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

## 구조

```
aiden-auto/
├── skills/        25개 (auto 진입점 + 카테고리별 chapter)
├── agents/        34개 (6 카테고리: core/domain/iteration/verification/creative/meta)
├── hooks/         25개 (lifecycle/quality/safety/integrations)
├── rules/          8개
├── references/    25개
├── commands/      20개
├── lib/           15개 (calendar/figma/gmail/jira/slack 등 + advisor/ai_auth 고유)
└── config/         3개 (platform/profile/eco)
```

## 라이선스

MIT

## 출처

- C:\claude v18.0 (hooks, commands, lib, embedded-critic)
- aiden-auto v27.2 (chapter routing, iteration V10.0, verification specialists)
