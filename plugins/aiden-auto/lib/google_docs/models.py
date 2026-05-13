"""
데이터 모델 정의

Google Docs 변환에 사용되는 데이터 클래스들을 정의합니다.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TextSegment:
    """인라인 텍스트 세그먼트 (스타일 정보 포함)"""

    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    strikethrough: bool = False
    link: Optional[str] = None
    # 이미지 관련 필드 (마크다운 ![alt](url) 구문)
    image_url: Optional[str] = None  # 이미지 URL (HTTP/HTTPS)
    image_alt: Optional[str] = None  # 이미지 alt 텍스트


@dataclass
class TableCell:
    """테이블 셀"""

    content: str
    segments: list[TextSegment] = field(default_factory=list)
    is_header: bool = False


@dataclass
class TableData:
    """마크다운 테이블 구조"""

    headers: list[str]
    rows: list[list[str]]
    column_count: int
    row_count: int
    column_alignments: list[str] = field(
        default_factory=list
    )  # 'left', 'center', 'right'


@dataclass
class InlineParseResult:
    """인라인 파싱 결과"""

    segments: list[TextSegment] = field(default_factory=list)
    plain_text: str = ""


@dataclass
class ConversionResult:
    """마크다운 → Google Docs 변환 결과"""

    requests: list[dict[str, Any]] = field(default_factory=list)
    headings: list[dict[str, Any]] = field(default_factory=list)  # 목차용
    table_locations: list[int] = field(default_factory=list)  # 테이블 위치
    final_index: int = 1  # 문서 끝 인덱스
