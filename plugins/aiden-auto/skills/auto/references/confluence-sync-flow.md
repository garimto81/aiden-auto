---
name: confluence-sync-flow
version: v28.5
loaded_from: chapter-doc, phase-minus-1.5-deep-interview
purpose: GG NETWORK Confluence 자동 sync 흐름
---

# Confluence Sync Flow

## 발동 조건

- 카테고리: DOC chapter 만 (CODE/QA 등에서는 skip)
- Phase 4 (저장 + 커밋) 단계 도달
- `active-goal.json` 의 `confluence_sync.enabled == true`

## 비유

> 본관 도서관 (로컬 docs/) → 회사 협력 도서관 (GG NETWORK Confluence) 자동 사본 전달.
> 작성자가 출고 결정 (Deep Interview Q5) → 시스템이 자동 운반.

## 전제 조건 자동 검증

| 항목 | 확인 방법 | 부재 시 |
|------|----------|--------|
| `ATLASSIAN_EMAIL` 환경변수 | `os.environ.get()` + winreg fallback | sync skip + 알림 |
| `ATLASSIAN_API_TOKEN` 환경변수 | 동일 | sync skip + 알림 |
| `CONFLUENCE_BASE_URL` | default: `https://ggnetwork.atlassian.net/wiki` | default 사용 |
| `lib/confluence/md2confluence.py` | 파일 존재 | sync skip + 에러 |
| API 인증 ping | GET `/rest/api/content?limit=1` | sync skip + 사용자 의뢰 |

## sync 흐름 다이어그램

```
   Phase 4.0  파일 저장 (docs/00-prd/...)
        │
        ▼
   Phase 4.1  git commit (Conventional Commit)
        │
        ▼
   Phase 4.2  Confluence Sync (NEW v28.5)
        │
        ├─ confluence_sync.enabled == false → skip
        │
        ├─ mode = "update"
        │  ├─ page_id 사용
        │  └─ python md2confluence.py <md_file> <page_id>
        │
        └─ mode = "new"
           ├─ parent_id 사용
           ├─ API: POST /rest/api/content
           │      title, parentId, space.key 명시
           └─ 새 page_id 회신 → active-goal.json 에 저장
        │
        ▼
   Phase 4.3  사용자 보고 (Confluence URL 포함)
```

## 실패 처리

| 실패 종류 | 처리 |
|---------|------|
| `md2confluence.py` 실행 실패 | 로컬 파일 유지, sync 실패만 알림. Phase 4 진행. |
| 환경변수 미설정 | Phase -1.5 Part C 자동 skip. Phase 4.2 도 skip. |
| 페이지 ID 잘못됨 (404) | 사용자에게 페이지 ID 확인 의뢰 |
| 인증 실패 (401/403) | 사용자에게 토큰 갱신 의뢰 |
| 네트워크 타임아웃 | 1회 재시도. 재실패 시 sync skip + 알림 |

## md2confluence.py 호출 패턴

```python
import subprocess
import json

def confluence_sync(md_file: str, page_id: str, dry_run: bool = False) -> dict:
    cmd = [
        "python",
        "C:/claude/lib/confluence/md2confluence.py",
        md_file,
        page_id,
    ]
    if dry_run:
        cmd.append("--dry-run")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "url": _parse_url(result.stdout),  # md2confluence 출력에서 URL 추출
    }
```

## Executive Summary 와의 연동

DOC chapter 에서 Executive Summary 가 별도 파일 (`{slug}.exec-summary.md`) 인 경우:

| 옵션 | 동작 |
|------|------|
| A (기본) | exec-summary 가 본문 페이지의 child 페이지로 sync |
| B (옵션) | exec-summary 가 본문 페이지의 첫 섹션으로 병합 후 sync |

A 가 기본 — 사용자가 Confluence 에서 빠른 1-page view 가능.

## 산출물

`active-goal.json` 의 `confluence_sync` 필드 갱신:

```json
{
  "confluence_sync": {
    "enabled": true,
    "mode": "update",
    "page_id": "1234567890",
    "synced_at": "2026-05-19T18:00:00Z",
    "synced_url": "https://ggnetwork.atlassian.net/wiki/pages/1234567890",
    "exec_summary_page_id": "1234567891"
  }
}
```

## 사용자 보고 예시

```
✅ Confluence sync 완료

  본문:           https://ggnetwork.atlassian.net/wiki/pages/1234567890
  Executive Summary: https://ggnetwork.atlassian.net/wiki/pages/1234567891

  버전: 12 (이전 11)
  공간: PROD
  부모: <부모 페이지 제목>
```

## 보안

- API token 은 환경변수에서만 읽음 — 코드/문서에 hardcode 금지
- token 누출 위험: `framework_edit_guard.py` 가 `.env` 파일 layer 간 sync 차단 (rule 19 v3.7 EXCLUDE 정책)
- Confluence 페이지 권한은 GG NETWORK Atlassian admin 정책에 따름
