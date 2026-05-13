"""
Google Docs Converter 에러 정의

모듈별 구조화된 예외 클래스를 제공합니다.
"""


class GoogleDocsError(Exception):
    """Google Docs 모듈 기본 예외"""

    pass


class GoogleDocsConverterError(GoogleDocsError):
    """Google Docs 변환 오류 기본 클래스"""

    pass


class TableRenderError(GoogleDocsConverterError):
    """테이블 렌더링 오류"""

    def __init__(self, message: str, table_index: int = 0, phase: str = "unknown"):
        super().__init__(f"Table #{table_index} ({phase}): {message}")
        self.table_index = table_index
        self.phase = phase


class IndexCalculationError(GoogleDocsConverterError):
    """인덱스 계산 오류"""

    def __init__(self, message: str, expected: int = 0, actual: int = 0):
        super().__init__(
            f"Index error: {message} (expected={expected}, actual={actual})"
        )
        self.expected = expected
        self.actual = actual


class AuthenticationError(GoogleDocsError):
    """인증 관련 오류"""

    pass


class DocumentNotFoundError(GoogleDocsError):
    """문서를 찾을 수 없음"""

    def __init__(self, doc_id: str):
        super().__init__(f"Document not found: {doc_id}")
        self.doc_id = doc_id


class APIError(GoogleDocsError):
    """Google API 호출 오류"""

    def __init__(self, message: str, status_code: int = 0):
        super().__init__(f"API Error ({status_code}): {message}")
        self.status_code = status_code
