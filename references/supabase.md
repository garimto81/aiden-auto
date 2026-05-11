---
title: Supabase 작업 규칙
impact: HIGH
section: supabase
paths:
  - "automation_hub/**/*"
  - "**/*supabase*"
  - "**/*.sql"
---

# Supabase 작업 규칙

## 핵심 원칙

**코드 작성 전 반드시 CLI로 실제 DB 스키마 확인**

## 필수 확인 절차

| 단계 | 명령어 | 목적 |
|:----:|--------|------|
| 1 | `supabase db dump --schema public` | 테이블/컬럼 구조 확인 |
| 2 | `supabase inspect db table-sizes` | 테이블 존재 여부 |
| 3 | `supabase db diff` | 로컬 vs 원격 DB 차이 |

## 작업 유형별 필수 명령

| 작업 | 명령어 | 확인 사항 |
|------|--------|----------|
| 테이블 조회 | `supabase db dump -t [테이블명]` | 컬럼명, 타입 |
| 테이블 생성 | `supabase inspect db table-sizes` | 중복 확인 |
| RLS 정책 | `supabase inspect db policies` | 정책 충돌 |
| 인덱스 추가 | `supabase inspect db index-sizes` | 기존 인덱스 |
| FK 설정 | `supabase db dump --schema public` | 참조 테이블 |

## 금지 사항

| 금지 | 이유 | 대안 |
|------|------|------|
| ❌ TypeScript 타입만 보고 가정 | outdated 가능 | CLI 확인 |
| ❌ 마이그레이션 파일만 확인 | 미적용 가능 | `db diff` |
| ❌ 테이블/컬럼 존재 가정 | 런타임 에러 | `db dump` |
| ❌ RLS 비활성화 가정 | 보안 이슈 | `inspect policies` |

## 스키마 확인 흐름

```
요청 접수
    │
    ▼
┌─────────────────────┐
│ supabase db dump    │ ← 필수 1단계
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│ TypeScript vs 실제  │ ← 필수 2단계
│ 타입 비교           │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│ 코드 작성/수정      │
└─────────────────────┘
```

## 체크리스트

```markdown
- [ ] `supabase db dump` 실행
- [ ] 테이블/컬럼 존재 확인
- [ ] TypeScript 타입 일치 확인
- [ ] 새 마이그레이션 필요 시 `supabase migration new`
```

## 상세 문서

`docs/SUPABASE_GUIDE.md`
