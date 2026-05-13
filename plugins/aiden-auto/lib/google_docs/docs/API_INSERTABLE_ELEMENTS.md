# Google Docs API 삽입 가능 형식 완전 리스트

**Version**: 1.0.0
**Last Updated**: 2026-01-30

Google Docs API에서 프로그래매틱하게 삽입/조작 가능한 모든 요소 타입 정리 문서입니다.

---

## 1. batchUpdate Request Types (37개)

프로그래매틱하게 **삽입/수정/삭제** 가능한 모든 요청 타입:

### 텍스트 조작

| Request Type | 설명 |
|--------------|------|
| `InsertTextRequest` | 텍스트 삽입 |
| `UpdateTextStyleRequest` | 텍스트 스타일 수정 |
| `ReplaceAllTextRequest` | 전체 텍스트 치환 |

### 단락 조작

| Request Type | 설명 |
|--------------|------|
| `UpdateParagraphStyleRequest` | 단락 스타일 수정 |
| `CreateParagraphBulletsRequest` | 불릿 리스트 생성 |
| `DeleteParagraphBulletsRequest` | 불릿 리스트 삭제 |

### 테이블 조작

| Request Type | 설명 |
|--------------|------|
| `InsertTableRequest` | 테이블 삽입 |
| `InsertTableRowRequest` | 테이블 행 삽입 |
| `InsertTableColumnRequest` | 테이블 열 삽입 |
| `DeleteTableRowRequest` | 테이블 행 삭제 |
| `DeleteTableColumnRequest` | 테이블 열 삭제 |
| `UpdateTableColumnPropertiesRequest` | 테이블 열 속성 수정 |
| `UpdateTableCellStyleRequest` | 테이블 셀 스타일 수정 |
| `UpdateTableRowStyleRequest` | 테이블 행 스타일 수정 |
| `MergeTableCellsRequest` | 셀 병합 |
| `UnmergeTableCellsRequest` | 셀 병합 해제 |
| `PinTableHeaderRowsRequest` | 헤더 행 고정 |

### 이미지 조작

| Request Type | 설명 |
|--------------|------|
| `InsertInlineImageRequest` | 인라인 이미지 삽입 |
| `ReplaceImageRequest` | 이미지 교체 |
| `DeletePositionedObjectRequest` | 위치 지정 객체 삭제 |

### 페이지/섹션 구조

| Request Type | 설명 |
|--------------|------|
| `InsertPageBreakRequest` | 페이지 브레이크 삽입 |
| `InsertSectionBreakRequest` | 섹션 브레이크 삽입 |
| `UpdateSectionStyleRequest` | 섹션 스타일 수정 |

### 머리글/바닥글/각주

| Request Type | 설명 |
|--------------|------|
| `CreateHeaderRequest` | 머리글 생성 |
| `CreateFooterRequest` | 바닥글 생성 |
| `CreateFootnoteRequest` | 각주 생성 |
| `DeleteHeaderRequest` | 머리글 삭제 |
| `DeleteFooterRequest` | 바닥글 삭제 |

### Named Range

| Request Type | 설명 |
|--------------|------|
| `CreateNamedRangeRequest` | Named Range 생성 |
| `DeleteNamedRangeRequest` | Named Range 삭제 |
| `ReplaceNamedRangeContentRequest` | Named Range 내용 교체 |

### 콘텐츠 삭제

| Request Type | 설명 |
|--------------|------|
| `DeleteContentRangeRequest` | 콘텐츠 범위 삭제 |

### 문서 전체 스타일

| Request Type | 설명 |
|--------------|------|
| `UpdateDocumentStyleRequest` | 문서 스타일 수정 |

### 문서 탭 (다중 탭 문서)

| Request Type | 설명 |
|--------------|------|
| `AddDocumentTabRequest` | 탭 추가 |
| `DeleteTabRequest` | 탭 삭제 |
| `UpdateDocumentTabPropertiesRequest` | 탭 속성 수정 |

### Person 삽입 (Smart Chip)

| Request Type | 설명 |
|--------------|------|
| `InsertPersonRequest` | Person Smart Chip 삽입 ✅ |

---

## 2. Structural Elements (4개)

문서의 최상위 구조 요소:

| Element | 설명 |
|---------|------|
| `Paragraph` | 단락 (가장 기본 요소) |
| `Table` | 테이블 |
| `SectionBreak` | 섹션 구분 |
| `TableOfContents` | 목차 |

---

## 3. Paragraph Elements (11개)

단락 내에 포함될 수 있는 요소들:

| Element | 설명 | API 삽입 |
|---------|------|----------|
| `TextRun` | 일반 텍스트 | ✅ `InsertTextRequest` |
| `AutoText` | 동적 텍스트 (페이지 번호 등) | ❌ 읽기 전용 |
| `PageBreak` | 페이지 브레이크 | ✅ `InsertPageBreakRequest` |
| `ColumnBreak` | 열 브레이크 | ❌ 직접 API 없음 |
| `InlineObjectElement` | 인라인 이미지 등 | ✅ `InsertInlineImageRequest` |
| `Person` | 사람 멘션 (Smart Chip) | ✅ `InsertPersonRequest` |
| `RichLink` | Google 리소스 링크 | ❌ **Output only** |
| `DateElement` | 날짜 (Smart Chip) | ❌ 읽기 전용 |
| `Equation` | 수식 | ❌ 직접 API 없음 |
| `HorizontalRule` | 수평선 | ❌ 직접 API 없음 |
| `FootnoteReference` | 각주 참조 | ✅ `CreateFootnoteRequest` |

---

## 4. 삽입 불가능한 요소 (API 미지원)

| 요소 | UI 기능 | API 지원 |
|------|---------|----------|
| **Code Block** | Insert > Building blocks > Code block | ❌ **미지원** |
| **Smart Chip (일부)** | @file, @event, @date | ❌ RichLink/Date는 Output only |
| **Building Blocks** | 체크리스트, 프로젝트 트래커 등 | ❌ **미지원** |
| **Equation** | 수식 편집기 | ❌ 직접 삽입 불가 |
| **Drawing** | 삽입 > 그림 | ❌ 직접 삽입 불가 |
| **Chart** | 차트 | ❌ 직접 삽입 불가 (Sheets 연동 필요) |

---

## 5. 핵심 결론

### 삽입 가능 ✅

- 텍스트, 스타일
- 테이블 (모든 조작 가능)
- 인라인 이미지
- Person Smart Chip (`InsertPersonRequest`)
- 머리글/바닥글/각주
- 페이지/섹션 브레이크

### 삽입 불가능 ❌

- **Code Block** (Building Blocks 전체 미지원)
- RichLink (읽기 전용)
- DateElement (읽기 전용)
- Equation (읽기 전용)
- HorizontalRule (직접 API 없음)
- ColumnBreak (직접 API 없음)

---

## 6. Code Block 대안 전략

Code Block이 API에서 지원되지 않으므로 다음 대안 사용:

### 옵션 A: 회색 배경 테이블 (권장)

```python
# 1x1 테이블에 코드 삽입 후 배경색 적용
{
    "insertTable": {
        "rows": 1,
        "columns": 1,
        "location": {"index": idx}
    }
}
# + updateTableCellStyle로 배경색 #f1f3f4 적용
# + 고정폭 폰트(Courier New) 적용
```

### 옵션 B: 들여쓰기 + 배경색

```python
# 텍스트 삽입 후 단락 스타일로 들여쓰기
{
    "updateParagraphStyle": {
        "paragraphStyle": {
            "indentStart": {"magnitude": 36, "unit": "PT"},
            "shading": {"backgroundColor": {"color": {"rgbColor": {"red": 0.95}}}}
        }
    }
}
```

### 현재 구현 (lib/google_docs/converter.py)

현재 시스템은 **옵션 A** 사용:
- 코드 블록 → 1x1 테이블로 변환
- 배경색: `#f1f3f4` (Google Docs 기본 코드 배경)
- 폰트: Courier New, 10pt

---

## Sources

- [Google Docs API Request Types](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/request)
- [Google Docs Document Structure](https://developers.google.com/workspace/docs/api/concepts/structure)
- [ParagraphElement Java API](https://googleapis.dev/java/google-api-services-docs/latest/com/google/api/services/docs/v1/model/ParagraphElement.html)
- [Google Workspace Updates - Code Blocks](https://workspaceupdates.googleblog.com/2025/04/additional-programming-languages-code-blocks-google-docs.html)

---

*Last Updated: 2026-01-30*
