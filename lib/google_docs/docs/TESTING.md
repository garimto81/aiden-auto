# Testing Guide

**Version**: 1.0.0
**Last Updated**: 2026-01-30

---

## 1. 개요

Google Docs Converter의 테스트 현황 및 실행 가이드입니다.

### 테스트 현황

| 테스트 파일 | 테스트 수 | 대상 모듈 | 프레임워크 |
|------------|----------|----------|-----------|
| `test_batch_processor.py` | 11 | BatchConverter, ConvertResult | pytest + asyncio |
| `test_auto_trigger.py` | 12 | AutoTriggerHandler | pytest + parametrize |
| `test_table_width_optimization.py` | 14 | NativeTableRenderer | pytest |
| **합계** | **37** | - | - |

### 커버리지 현황

| 모듈 | 테스트 여부 | 비고 |
|------|-----------|------|
| `batch_processor.py` | ✅ 테스트됨 | 10 tests |
| `auto_trigger.py` | ✅ 테스트됨 | 12 tests |
| `table_renderer.py` | ✅ 테스트됨 | 14 tests |
| `converter.py` | ⚠️ 부분 | Mock 통합 테스트 |
| `image_inserter.py` | ⚠️ 부분 | Mock 통합 테스트 |
| `cli.py` | ⚠️ 부분 | Mock 통합 테스트 |
| `auth.py` | ❌ 미테스트 | OAuth 수동 테스트 |
| `models.py` | ❌ 미테스트 | 데이터 클래스 |

---

## 2. 빠른 시작

### 전체 테스트 실행

```powershell
# 모든 테스트 실행
pytest C:\claude\lib\google_docs\tests\ -v

# 커버리지 포함
pytest C:\claude\lib\google_docs\tests\ -v --cov=lib.google_docs

# HTML 커버리지 리포트
pytest C:\claude\lib\google_docs\tests\ -v --cov=lib.google_docs --cov-report=html
start htmlcov/index.html
```

### 개별 테스트 실행 (권장)

```powershell
# BatchConverter 테스트
pytest C:\claude\lib\google_docs\tests\test_batch_processor.py -v

# AutoTrigger 테스트
pytest C:\claude\lib\google_docs\tests\test_auto_trigger.py -v

# 테이블 너비 최적화 테스트
pytest C:\claude\lib\google_docs\tests\test_table_width_optimization.py -v
```

### 특정 테스트 함수 실행

```powershell
# 단일 테스트 함수
pytest C:\claude\lib\google_docs\tests\test_batch_processor.py::TestBatchConverter::test_init_default -v

# 테스트 클래스
pytest C:\claude\lib\google_docs\tests\test_auto_trigger.py::TestAutoTriggerHandler -v
```

---

## 3. 테스트 파일 상세

### 3.1 test_batch_processor.py (11 tests)

**대상 모듈**: `batch_processor.py` (BatchConverter, ConvertResult)

#### TestBatchConverter (9 tests)

| 테스트 | 목적 | 사용 기술 |
|--------|------|----------|
| `test_init_default` | 기본 초기화 검증 | - |
| `test_init_custom` | 커스텀 설정 검증 | - |
| `test_read_file` | 파일 읽기 기능 | tmp_path fixture |
| `test_convert_batch_empty` | 빈 리스트 처리 | @pytest.mark.asyncio |
| `test_convert_single_success` | 단일 변환 성공 | Mock, asyncio |
| `test_convert_single_failure` | 단일 변환 실패 | asyncio |
| `test_convert_directory_invalid` | 잘못된 디렉토리 | pytest.raises |
| `test_convert_directory_no_files` | 빈 디렉토리 | tmp_path |
| `test_convert_directory_success` | 디렉토리 변환 성공 | Mock |

#### TestConvertResult (2 tests)

| 테스트 | 목적 |
|--------|------|
| `test_success_result` | 성공 결과 데이터 생성 |
| `test_failure_result` | 실패 결과 데이터 생성 |

**주요 패턴**:
- `@pytest.mark.asyncio`: 비동기 함수 테스트
- `@patch()`: 외부 API 호출 Mock
- `tmp_path`: 임시 파일 생성

---

### 3.2 test_auto_trigger.py (12 tests)

**대상 모듈**: `auto_trigger.py` (AutoTriggerHandler)

#### TestAutoTriggerHandler (12 tests)

| 테스트 | 목적 | 사용 기술 |
|--------|------|----------|
| `test_init_default` | 기본 초기화 | - |
| `test_init_custom` | 커스텀 폴더 ID | - |
| `test_should_trigger_keywords` | 키워드 트리거 (8 cases) | @pytest.mark.parametrize |
| `test_should_trigger_file_patterns` | 파일 패턴 트리거 (5 cases) | @pytest.mark.parametrize |
| `test_should_trigger_combined` | 키워드 + 패턴 조합 | - |
| `test_execute_success` | 변환 실행 성공 | Mock, tmp_path |
| `test_execute_with_string_content` | 문자열 변환 | Mock |
| `test_suggest_conversion_prd_file` | PRD 파일 제안 | tmp_path |
| `test_suggest_conversion_regular_md` | 일반 MD 제안 | tmp_path |
| `test_suggest_conversion_nonexistent_file` | 존재하지 않는 파일 | - |
| `test_suggest_conversion_non_markdown` | 비 마크다운 파일 | tmp_path |
| `test_suggest_conversion_large_file` | 큰 파일 (1MB+) | tmp_path |

**주요 패턴**:
- `@pytest.mark.parametrize`: 다중 입력 케이스 테스트
- 키워드 트리거: `"prd to gdocs"`, `"convert to google docs"`, `"--to-gdocs"` 등
- 파일 패턴: `"tasks/prds/PRD-*.md"`, `"docs/prds/*.md"` 등

---

### 3.3 test_table_width_optimization.py (14 tests)

**대상 모듈**: `table_renderer.py` (NativeTableRenderer)

Single-Line First 전략 검증:
1. 짧은 텍스트는 한 줄 표시
2. 긴 텍스트는 남은 공간에서 유연 분배
3. 총 너비는 510pt (18cm) 유지

#### TestTextWidthCalculation (4 tests)

| 테스트 | 목적 | 검증 내용 |
|--------|------|----------|
| `test_ascii_text_width` | ASCII 너비 계산 | 5글자 × 6.5pt + 패딩 10pt = 42.5pt |
| `test_korean_text_width` | 한글 너비 계산 | 2글자 × 12pt + 패딩 10pt = 34pt |
| `test_mixed_text_width` | 혼합 텍스트 너비 | ASCII + 한글 혼합 계산 |
| `test_empty_text_width` | 빈 텍스트 처리 | 0.0pt 반환 |

#### TestSingleLineOptimization (4 tests)

| 테스트 | 목적 |
|--------|------|
| `test_all_short_columns` | 모든 컬럼이 짧은 경우 (정확한 너비 할당) |
| `test_mixed_columns` | 짧은 + 긴 컬럼 혼합 (짧은 컬럼 우선) |
| `test_all_long_columns` | 모든 컬럼이 긴 경우 (비율 분배) |
| `test_single_line_budget_limit` | 한 줄 예산 70% 초과 시 축소 |

#### TestDynamicColumnWidths (4 tests)

| 테스트 | 목적 |
|--------|------|
| `test_simple_table` | 간단한 테이블 (ID, Name, Description) |
| `test_korean_table` | 한글 테이블 (번호, 이름, 설명) |
| `test_empty_table` | 빈 테이블 (빈 배열 반환) |
| `test_single_column` | 단일 컬럼 테이블 (전체 너비 사용) |

#### TestWidthConstraints (2 tests)

| 테스트 | 목적 |
|--------|------|
| `test_minimum_width` | 최소 너비 보장 (MIN_COLUMN_WIDTH_PT) |
| `test_maximum_width` | 최대 너비 제한 (MAX_COLUMN_WIDTH_PT) |

**핵심 검증**:
- 총 너비: `sum(widths) == 510pt` (허용 오차 1pt)
- 비율 유지: 짧은 컬럼 < 긴 컬럼
- 제약 조건: MIN_COLUMN_WIDTH_PT ≤ width ≤ MAX_COLUMN_WIDTH_PT

---

## 4. 테스트 패턴 가이드

### 4.1 Fixture 사용

```python
@pytest.fixture
def temp_md_files(tmp_path):
    """임시 마크다운 파일 생성"""
    files = []
    for i in range(3):
        file = tmp_path / f"test_{i}.md"
        file.write_text(f"# Test Document {i}\n\nContent {i}", encoding="utf-8")
        files.append(file)
    return files

def test_read_file(temp_md_files):
    converter = BatchConverter()
    content = converter._read_file(temp_md_files[0])
    assert "Test Document 0" in content
```

**장점**:
- 테스트 격리 (각 테스트마다 새 파일)
- 자동 정리 (테스트 후 tmp_path 자동 삭제)
- 재사용성 (여러 테스트에서 동일 fixture 사용)

---

### 4.2 Mock 사용

```python
@patch("lib.google_docs.batch_processor.create_google_doc")
async def test_convert_single_success(mock_create, temp_md_files):
    mock_create.return_value = "https://docs.google.com/document/d/test123"

    converter = BatchConverter()
    result = await converter._convert_single(temp_md_files[0])

    assert result.success is True
    assert result.doc_url == "https://docs.google.com/document/d/test123"
```

**용도**:
- 외부 API 호출 방지 (Google Docs API)
- 성공/실패 시나리오 시뮬레이션
- 빠른 테스트 실행

---

### 4.3 Parametrize 사용

```python
@pytest.mark.parametrize(
    "user_input,expected",
    [
        ("prd to gdocs", True),
        ("convert to google docs", True),
        ("md to docs", True),
        ("--to-gdocs", True),
        ("일반 텍스트", False),
        ("", False),
    ],
)
def test_should_trigger_keywords(user_input, expected):
    handler = AutoTriggerHandler()
    result = handler.should_trigger(user_input=user_input)
    assert result == expected
```

**장점**:
- 다양한 입력 케이스 테스트
- 코드 중복 제거
- 테스트 케이스 명확성

---

### 4.4 Asyncio 테스트

```python
@pytest.mark.asyncio
async def test_convert_batch_empty():
    converter = BatchConverter()
    results = await converter.convert_batch([])
    assert results == []
```

**설정**:
- `pytest-asyncio` 설치 필요: `pip install pytest-asyncio`
- `@pytest.mark.asyncio` 데코레이터 사용
- `async def` 함수로 작성

---

### 4.5 예외 테스트

```python
def test_convert_directory_invalid():
    converter = BatchConverter()

    with pytest.raises(ValueError, match="디렉토리가 아닙니다"):
        converter.convert_directory(Path("nonexistent_dir"))
```

**용도**:
- 에러 핸들링 검증
- 예외 메시지 확인

---

## 5. 실행 환경

### 5.1 의존성

```powershell
# 테스트 실행에 필요한 패키지
pip install pytest
pip install pytest-asyncio
pip install pytest-cov
```

### 5.2 환경 변수

테스트는 Mock을 사용하므로 실제 Google API 인증 불필요.

```powershell
# 필수 아님 (Mock 사용)
# set GOOGLE_DOCS_FOLDER_ID=test_folder
```

### 5.3 주의사항

| 항목 | 설명 |
|------|------|
| **타임아웃** | 전체 테스트 실행 시 120초 초과 시 크래시 위험 |
| **권장 방법** | 개별 파일 또는 클래스 단위로 실행 |
| **Background 모드** | 전체 테스트는 background 모드 권장 |
| **Mock 확인** | `@patch()` 경로가 정확한지 확인 |

---

## 6. 커버리지 현황

### 6.1 테스트된 모듈

| 모듈 | 커버리지 | 테스트 수 | 비고 |
|------|----------|----------|------|
| `batch_processor.py` | 85%+ | 10 | 비동기 로직 포함 |
| `auto_trigger.py` | 90%+ | 12 | 키워드/패턴 트리거 |
| `table_renderer.py` | 95%+ | 14 | 너비 계산 알고리즘 |

### 6.2 미테스트 모듈

| 모듈 | 우선순위 | 테스트 계획 |
|------|----------|------------|
| `auth.py` | LOW | OAuth는 수동 테스트 |
| `converter.py` | MEDIUM | 통합 테스트 추가 필요 |
| `image_inserter.py` | MEDIUM | Mock 기반 단위 테스트 |
| `cli.py` | HIGH | CLI 인터페이스 테스트 |
| `models.py` | LOW | 데이터 클래스, 테스트 불필요 |

---

## 7. 테스트 추가 가이드

### 새 테스트 파일 생성

```powershell
# tests 디렉토리에 생성
New-Item -ItemType File -Path "C:\claude\lib\google_docs\tests\test_new_module.py"
```

### 테스트 파일 구조

```python
"""
모듈명 단위 테스트
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from ..module_name import ClassName


@pytest.fixture
def setup_data():
    """테스트 데이터 설정"""
    return {"key": "value"}


class TestClassName:
    """ClassName 테스트"""

    def test_basic_functionality(self):
        """기본 기능 테스트"""
        obj = ClassName()
        assert obj.method() == expected_value
```

### 네이밍 컨벤션

| 항목 | 패턴 | 예시 |
|------|------|------|
| 파일명 | `test_*.py` | `test_converter.py` |
| 클래스명 | `Test<ClassName>` | `TestBatchConverter` |
| 함수명 | `test_<description>` | `test_convert_success` |
| Fixture | `<description>_data` | `temp_md_files` |

---

## 8. CI/CD 통합

### GitHub Actions (예시)

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest C:\claude\lib\google_docs\tests\ -v --cov=lib.google_docs
```

---

## 관련 문서

| 문서 | 위치 |
|------|------|
| 빌드/테스트 규칙 | `C:\claude\.claude\rules\07-build-test.md` |
| TDD 규칙 | `C:\claude\.claude\rules\04-tdd.md` |
| 변환 프로세스 | `C:\claude\lib\google_docs\docs\CONVERSION_PROCESS.md` |

---

*Last Updated: 2026-01-30*
