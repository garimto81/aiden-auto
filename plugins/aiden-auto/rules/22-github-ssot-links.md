# GitHub = 문서 SSOT — 참조 링크는 항상 GitHub 기준 (사용자 결정 2026-06-08)

> **사용자 결정 2026-06-08**: 같은 문서가 로컬·GitHub·Confluence·Figma 등 여러 곳에 공유될 때, **링크/참조는 항상 GitHub 정본(canonical)을 가리킨다.** GitHub 가 문서 내용의 단일 정본(SSOT)이다.

---

## 핵심 정책

문서가 여러 플랫폼에 흩어져 있어도 **진짜 원본은 GitHub 하나**다. 다른 곳(Confluence/Figma/로컬 사본)은 전부 "복사본"이며, 문서 안에서 다른 문서를 가리키는 링크는 **무조건 GitHub 주소**로 건다.

```
                    ┌──────────────────────┐
                    │   GitHub  (정본 SSOT) │ ◄── 모든 참조 링크가 여기를 가리킴
                    └──────────┬───────────┘
                               │ 복사/배포
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
       Confluence           Figma              로컬 사본
       (복사본)            (복사본)            (복사본)
       링크 → GitHub       링크 → GitHub       링크 → GitHub
```

> 비유: 책의 진짜 원고는 출판사(GitHub) 한 곳에만 있다. 도서관(Confluence)·전시장(Figma)에 둔 사본 안에서 "다른 챕터 보기"를 누르면, 그 사본이 아니라 **출판사 원고**로 안내한다. 그래야 누가 어디서 보든 같은 최신 원본에 도달한다.

---

## 링크 형태 (사용자 결정)

| 항목 | 결정 | 의미 |
|------|------|------|
| **기준 브랜치** | `main` (항상 최신) | 링크는 늘 GitHub 현재 버전으로 감. 문서는 살아있는 정본이므로 최신을 보여줌 |
| **기존 외부 링크** | **GitHub로 완전 교체** | Confluence/Figma 안의 상호 참조 링크를 전부 GitHub 주소로 바꿈 (페이지-내-링크 유지 X) |
| **URL 형태** | `https://github.com/{owner}/{repo}/blob/main/{경로}` | git remote 에서 자동 계산 — 문서마다 주소를 손으로 적을 필요 없음 |

- "그때 시점 고정(commit permalink)" 은 채택 안 함 — 정본 추적 목적과 안 맞음.
- 단점(파일 이름/위치 변경 시 옛 링크 깨짐)은 감수. 파일 이동 시 링크 재생성으로 대응.

---

## 자동 동작 (구현 위치)

`lib/confluence/md2confluence.py` 가 Markdown → Confluence 변환 시 자동 적용:

| 함수 | 동작 |
|------|------|
| `derive_github_base()` | `git remote get-url origin` 에서 `owner/repo` 추출 → `.../blob/main` base 생성. GitHub remote 없으면 빈 문자열(자동 fallback) |
| `github_url_for()` | repo 상대경로 → GitHub 정본 URL (경로 공백은 `%20` 인코딩) |
| `_linkify_path()` | frontmatter 인과관계 박스(📌 정본·🔗 관련 문서)의 링크를 GitHub 우선으로 |
| `transform_cross_links()` | 본문 `<a href="../X.md">` 상호참조를 GitHub 정본 URL로 교체 |

**우선순위**: in-repo `.md` + GitHub remote 존재 → **GitHub 정본 URL** (1순위). GitHub remote 없을 때만 기존 Confluence 링크(URL→page-id) fallback.

```
  cross-link 발견 (../Overview.md)
        │
        ▼
  in-repo + 파일 존재 + GitHub remote?
        │
   YES ─┴─ NO
    │       │
    ▼       ▼
 GitHub   Confluence fallback
 정본 URL  (url → page-id → <code>)
```

---

## 예외 / 탈출구 (escape hatch)

| 환경변수 | 효과 |
|----------|------|
| `GITHUB_SSOT=0` | GitHub SSOT 링크 비활성화 → 기존 Confluence 링크 동작으로 복귀 |
| `GITHUB_SSOT_BRANCH=<branch>` | 기준 브랜치 변경 (기본 `main`) |

- GitHub remote 가 없는 프로젝트는 자동으로 기존 동작 유지 (graceful fallback) — 별도 설정 불필요.

---

## Figma 처리

Figma 에는 문서 링크를 자동 재작성하는 코드가 없다 (`lib/figma/url_parser.py` 는 들어오는 Figma URL 파싱만 함). 따라서 Figma 는 **규약**으로 처리:

- Figma 파일/프레임 설명에 원본을 링크할 때는 **GitHub 정본 URL** 을 적는다.
- Figma 내부 링크를 다른 Figma/Confluence 로 걸지 않는다.

---

## rule 19 와의 구분 (혼동 주의)

| 규칙 | SSOT 대상 |
|------|----------|
| **rule 19** (plugin-ssot-policy) | **코드/설정 파일** 미러링 — `~/.claude/` 정본 → 3 mirror 동기화 |
| **rule 22** (본 규칙) | **문서 내용의 참조 링크** — GitHub 정본 URL 로 통일 |

서로 다른 층위다. rule 19 는 프레임워크 파일 동기화, rule 22 는 문서 안 링크 대상.

---

## 적용 범위

본 규칙은 **모든 프로젝트의 문서 동기화**에 적용:

- `/auto` 워크플로우 Confluence sync (Phase 4.2, `--con` 옵션)
- `md2confluence.py` 를 거치는 모든 Markdown → Confluence 변환
- 기획 문서(`docs/`)의 상호 참조 링크

---

## 변경 이력

| 날짜 | 변경 | 사유 |
|------|------|------|
| 2026-06-08 | 본 규칙 신규 작성 | 사용자 결정 — GitHub = 문서 SSOT, 참조 링크 항상 GitHub (main, 완전 교체) |

---

## 관련

- `lib/confluence/md2confluence.py` (`derive_github_base` / `github_url_for` / `_linkify_path` / `transform_cross_links`)
- `lib/confluence/test_md2confluence_github_ssot.py` (검증 13 케이스)
- `~/.claude/skills/auto/references/confluence-sync-flow.md` (Confluence sync 흐름)
- `~/.claude/rules/19-plugin-ssot-policy.md` (코드 파일 SSOT — 별개 층위)
- `~/.claude/rules/000-CHANGELOG.md` (rules 거버넌스)
