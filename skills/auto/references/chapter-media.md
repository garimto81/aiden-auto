---
name: chapter-media
category: MEDIA
pipeline: [triage, chapter-media]
next-skill: chapter-code  # 디자인 후 구현 가능
handoff: .claude/state/auto/media-{slug}.md
agent_team: [designer, writer, executor, critic, verifier]
phase_path: [-2, -1, 0, 1, 2, 4, cleanup]
---

# Chapter: MEDIA — UI 목업 / 영상 / 이미지 / 디자인

> **카테고리**: MEDIA (방송 도메인 친화)
> **트리거 키워드**: 목업, mockup, UI, 디자인, 화면, 와이어프레임, 영상, 이미지, 스크린샷
> **v27.2 강화**: XML + verifier + Cleanup

<Purpose>
사용자의 UI/디자인 요구를 받아 컨셉 → 명세 → 생성 → 미리보기 사이클로 자율 처리. 3-Tier 라우팅 (ASCII / HTML / Stitch+Figma) 자동 선택.
</Purpose>

<Use_When>
- UI 목업 ("화면 디자인", "와이어프레임")
- Figma 디자인 ("--figma <url>")
- 스크린샷 분석 ("이 화면 분석")
- 영상 메타데이터 (FFmpeg)
- 디자인 시스템 (frontend-design 스킬)
</Use_When>

<Workflow_Diagram>

```
[Triage: MEDIA]
      │
      ▼
Phase 0 (3-Tier 라우팅)
   Tier 1: ASCII (빠른 컨셉)
   Tier 2: HTML (B&W Refined)
   Tier 3: Stitch / Figma (고품질)
      │
      ▼
Phase 1 (컨셉 + 명세)
   ├─ designer: 무드보드
   └─ writer: 명세
      │
      ▼
Phase 2 (생성)
   mockup-hybrid 스킬 위임
      │
      ▼
Phase 2.5 (Multi-perspective Validation, NEW v27.2)
   ├── critic: 디자인 일관성
   └── verifier: 미리보기 가능 여부
      │
      ▼
Phase 4 (저장 + 미리보기 URL)
      │
      ▼
Phase Cleanup (NEW)
```

</Workflow_Diagram>

<Steps>

## Phase 0 — 3-Tier 라우팅

| Tier | 출력 | 사용 시점 |
|:----:|------|----------|
| 1 | ASCII | 빠른 컨셉 확인 |
| 2 | HTML (B&W Refined Minimal 기본) | 표준 목업 |
| 3 | Stitch / Figma | 고품질 최종 |

## Phase 1.1 — 무드보드 (designer)

```
designer 호출:
  · WebFetch (참고 사이트)
  · frontend-design 가이드라인
  · 방송 도메인 비유 활용 (사용자 친화)
  
  output:
    style_keywords
    color_palette
    layout_principle
    reference_examples
```

## Phase 1.2 — 명세 (writer)

```
docs/mockups/{feature}-spec.md
  · 화면 구성 요소
  · 인터랙션 명세
  · 반응형 규칙
  · 접근성 (WCAG)
```

## Phase 2 — 생성

```
mockup-hybrid 스킬 호출:
  Tier 결정 결과에 따라 자동 라우팅
  HTML 사이즈 규약: max-width 720, max-height 1280
```

## Phase 2.5 — Multi-perspective Validation (NEW v27.2)

```
critic + verifier 병렬:
  critic: 디자인 일관성, 사용자 도메인 친화
  verifier: 파일 실제 생성, 미리보기 가능 (브라우저 open)
```

## Phase 4 — 저장 + 미리보기

```
HTML: docs/mockups/{feature}.html
명세: docs/mockups/{feature}-spec.md
이미지: docs/images/{feature}/

git commit: docs(mockup): {feature} 화면 디자인
사용자 보고: 미리보기 경로
```

## Phase Cleanup (NEW v27.2)

```bash
rm -f .claude/state/auto/media-{slug}.json
TeamDelete()
```

</Steps>

<User_Friendly_Explanation>

```
"화면 디자인 작업이군요. 이렇게 진행할게요:

  1단계: 어떤 느낌으로 갈지 컨셉 (방송 콘티 짜듯)
  2단계: 참고 자료 모으고 무드보드
  3단계: 실제 화면 코드 생성
  4단계: 일관성 + 미리보기 가능 검증
  5단계: 저장 + 브라우저 링크
  6단계: 작업 흔적 정리"
```

</User_Friendly_Explanation>
