# ML 보조 판단 (Adaptive Mode)

> **출처**: C:/claude v18.2 SKILL.md L216-238 (critic 분석 후 흡수, 2026-05-11)
> **사용자 메모리 단서**: `project_ml_harness.md` — ML 자율 진화 라우팅, Shadow Mode 구현 완료
> **5원칙 매핑**: #5 슈퍼앱 (자율 진화) + #2 자가개선 (ML이 점수 예측 정확도 자체를 학습)
> **로드 시점**: 복잡도 산정(adaptive-phase-selection.md) 직후, ML 세션 활성 시만.

## 활성 조건

`.claude/ml/.ml_session_state.json` 파일이 존재해야 활성. 없으면 ML 보조 전체 스킵 (manual 점수만 사용).

```
ml_state_path = ".claude/ml/.ml_session_state.json"
if not file_exists(ml_state_path):
  return  # ML 비활성, 기존 수동 점수 사용
```

## 3가지 Mode

| Mode | 라우팅 기준 | 용도 |
|------|-----------|------|
| **Shadow** | manual 점수 사용, ML 예측은 *기록만* | 초기 학습. ML 정확도 누적 데이터 확보 |
| **Hybrid** | ML confidence ≥ 0.8 → ML 점수, 아니면 manual | 검증 단계. 고확신만 ML 신뢰 |
| **Primary** | ML 점수 우선, confidence < 0.5 → manual fallback | ML 검증 완료 후 정착 |

Mode는 `.ml_session_state.json` 내 `mode` 필드로 결정.

## 판단 로그 출력 (항상)

ML 활성 시 복잡도 산정 결과에 다음 줄을 *추가*:

```
═══ 복잡도 판단 ═══
파일 범위: {0|1}점 ({근거})
아키텍처: {0|1}점 ({근거})
의존성:   {0|1}점 ({근거})
모듈 영향: {0|1}점 ({근거})
사용자 명시: {0|1}점
총점: {manual_score}/5 → {Ralplan 실행|단독}
ML 예측: {ml_score}/5 (confidence: {conf}) [{shadow|hybrid|primary}]   ← NEW
═══════════════════
```

## 자가개선 사이클 연결

이 reference는 *외부 harness framework 자가개선* (`external-harness-registry.md`)과 별개로, **내부 ML 라우팅 자체의 자가개선** 메커니즘. 두 사이클이 함께 작동:

```
외부 harness 업데이트         내부 ML 학습
(harness-watcher 매일)    +   (manual vs ML 예측 누적)
       ↓                          ↓
이 plugin의 워크플로우 진화 ←──────┘
       ↓
사용자 진입점은 그대로 (Core Philosophy)
```

## 흡수 시 정제 사항 (옛 1480줄 대비)

- 모드 전환 트리거 명세 추가 (옛 본문은 *결과만* 기술, 전환 조건 부재)
- 활성 조건 1줄로 압축 (옛 본문은 산만)
- 외부 harness 자가개선과의 관계 명시 (옛 본문은 ML만 고립 설명)

## 관련 파일

- 활성 상태: `.claude/ml/.ml_session_state.json`
- 학습 데이터: `.claude/ml/training/` (manual vs ML 점수 기록)
- 복잡도 룰 본체: `references/adaptive-phase-selection.md`
