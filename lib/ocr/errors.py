"""
lib.ocr.errors - OCR 모듈 에러 클래스

Tesseract OCR 실행 중 발생 가능한 에러 계층 구조 정의.
"""


class OCRError(Exception):
    """OCR 모듈 기본 에러 클래스"""
    pass


class TesseractNotFoundError(OCRError):
    """Tesseract 바이너리 미발견"""
    pass


class ImageLoadError(OCRError):
    """이미지 로드 실패"""
    pass


class LanguagePackError(OCRError):
    """언어팩 누락"""
    pass


class PreprocessingError(OCRError):
    """이미지 전처리 실패"""
    pass


class TableDetectionError(OCRError):
    """표 감지 실패"""
    pass
