"""
lib.ocr - Tesseract OCR 정밀 텍스트 추출 모듈

Example:
    >>> from lib.ocr import OCRExtractor, ImagePreprocessor
    >>> extractor = OCRExtractor("invoice.jpg", lang="kor+eng")
    >>> result = extractor.extract_text(preprocess=True)
    >>> print(result.text)
"""

from .extractor import OCRExtractor
from .preprocessor import ImagePreprocessor
from .models import (
    OCRResult,
    TextRegion,
    TableDetection,
    LayoutInfo,
    BBox,
    AnalysisResult,
)
from .errors import (
    OCRError,
    TesseractNotFoundError,
    ImageLoadError,
    LanguagePackError,
    PreprocessingError,
    TableDetectionError,
)
from .graphic_detector import GraphicDetector
from .som_annotator import SoMAnnotator
from .hybrid_pipeline import HybridPipeline
from .models import UIElement, HybridAnalysisResult

__version__ = "1.0.0"

__all__ = [
    # 핵심 클래스
    "OCRExtractor",
    "ImagePreprocessor",
    # 데이터 모델
    "OCRResult",
    "TextRegion",
    "TableDetection",
    "LayoutInfo",
    "BBox",
    "AnalysisResult",
    # 에러
    "OCRError",
    "TesseractNotFoundError",
    "ImageLoadError",
    "LanguagePackError",
    "PreprocessingError",
    "TableDetectionError",
    # Hybrid Pipeline (신규)
    "GraphicDetector",
    "SoMAnnotator",
    "HybridPipeline",
    "UIElement",
    "HybridAnalysisResult",
]


def extract_text(image_path: str, lang: str = "kor+eng", preprocess: bool = True) -> str:
    """
    편의 함수: 이미지에서 텍스트 추출 (one-liner)

    Args:
        image_path: 이미지 파일 경로
        lang: 언어 코드 (기본값: "kor+eng")
        preprocess: 전처리 활성화 여부

    Returns:
        str: 추출된 텍스트

    Example:
        >>> from lib.ocr import extract_text
        >>> text = extract_text("receipt.jpg")
        >>> print(text)
    """
    extractor = OCRExtractor(image_path, lang=lang)
    result = extractor.extract_text(preprocess=preprocess)
    return result.text


def check_installation() -> dict:
    """
    Tesseract 설치 상태 검증

    Returns:
        dict: 설치 상태 정보
            - installed (bool): Tesseract 설치 여부
            - version (str): Tesseract 버전
            - languages (list): 사용 가능 언어팩
            - path (str): tesseract 실행 파일 경로

    Example:
        >>> from lib.ocr import check_installation
        >>> info = check_installation()
        >>> if not info["installed"]:
        ...     print("Install Tesseract: scoop install tesseract")
    """
    import pytesseract

    try:
        version = pytesseract.get_tesseract_version()
        languages = pytesseract.get_languages()
        cmd = pytesseract.pytesseract.tesseract_cmd

        return {
            "installed": True,
            "version": str(version),
            "languages": languages,
            "path": str(cmd),
        }
    except Exception as e:
        return {
            "installed": False,
            "version": None,
            "languages": [],
            "path": None,
            "error": str(e),
        }
