# Google Docs Converter Documentation

**Version**: 1.5.0
**Last Updated**: 2026-01-30

---

## 문서 목록

| 문서 | 설명 | 대상 |
|------|------|------|
| [CONVERSION_PROCESS.md](./CONVERSION_PROCESS.md) | **전체 변환 프로세스 설계** (6단계) | 모든 사용자 |
| [BATCH_PROCESSOR_GUIDE.md](./BATCH_PROCESSOR_GUIDE.md) | 배치 변환 및 자동 트리거 가이드 | 개발자 |
| [API_INSERTABLE_ELEMENTS.md](./API_INSERTABLE_ELEMENTS.md) | **API 삽입 가능 형식 완전 리스트** (37개 Request) | 개발자 |
| [TESTING.md](./TESTING.md) | **테스트 가이드** (36개 테스트, Fixture/Mock/Parametrize) | 개발자 |

---

## 빠른 시작

### CLI 변환

```bash
# 단일 파일
python -m lib.google_docs convert "C:\path\to\file.md"

# 배치 변환
python -m lib.google_docs batch "C:\path\to\*.md"
```

### Python API

```python
from lib.google_docs import create_google_doc

url = create_google_doc(
    title="문서 제목",
    content=markdown_content
)
```

---

## 변환 프로세스 요약

```
Markdown → 전처리 → 파싱 → 문서 생성 → 콘텐츠 삽입 → 이미지 처리 → Google Docs URL
```

| Stage | 설명 |
|:-----:|------|
| 1 | **전처리**: YAML 제거, 참조 링크, 괄호 영문 삭제, HTML 원본 삭제 |
| 2 | **파싱**: 마크다운 요소 식별, 인라인 포맷팅, API 요청 생성 |
| 3 | **문서 생성**: 빈 문서 생성, 폴더 이동, 페이지 스타일 적용 |
| 4 | **콘텐츠 삽입**: 텍스트, 테이블 2단계 처리, 코드 블록 |
| 5 | **이미지 처리**: Drive 업로드, Placeholder 교체 |
| 6 | **마무리**: 줄간격 115%, URL 반환 |

상세 내용: [CONVERSION_PROCESS.md](./CONVERSION_PROCESS.md)

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 네이티브 테이블 | 2단계 처리로 안정적 렌더링 |
| 이미지 자동 업로드 | 로컬 이미지 → Drive → Docs |
| 깨진 링크 필터링 | 로컬 경로, HTML 링크 자동 제외 |
| Rate Limit 처리 | 429 에러 시 지수 백오프 재시도 |
| 배치 변환 | 병렬 처리 (기본 3개 동시) |
| 자동 트리거 | 키워드/패턴 기반 자동 변환 |

---

## 관련 문서

| 문서 | 위치 |
|------|------|
| Google Workspace 스킬 | `C:\claude\.claude\skills\google-workspace\SKILL.md` |
| PRD 동기화 커맨드 | `C:\claude\.claude\commands\prd-sync.md` |
| 아카이브 PRD | `C:\claude\WSOPTV\tasks\prds\_archive\PRD-0003-md-to-gdocs-converter.md` |

---

*Last Updated: 2026-01-30*
