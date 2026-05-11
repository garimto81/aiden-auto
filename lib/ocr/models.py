"""
lib.ocr.models - OCR 데이터 모델

Tesseract OCR 추출 결과를 위한 dataclass 모델 정의.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BBox:
    """바운딩 박스 (좌표 + 크기)"""
    x: int
    y: int
    width: int
    height: int

    def area(self) -> int:
        """면적 계산"""
        return self.width * self.height

    def contains(self, other: "BBox") -> bool:
        """다른 BBox를 포함하는지 검사"""
        return (
            self.x <= other.x and
            self.y <= other.y and
            self.x + self.width >= other.x + other.width and
            self.y + self.height >= other.y + other.height
        )


@dataclass
class Word:
    """단어 레벨 정보"""
    text: str
    bbox: BBox
    confidence: float


@dataclass
class Line:
    """줄 레벨 정보"""
    words: List[Word]
    bbox: BBox

    @property
    def text(self) -> str:
        """줄의 전체 텍스트"""
        return " ".join(word.text for word in self.words)


@dataclass
class Paragraph:
    """문단 레벨 정보"""
    lines: List[Line]
    bbox: BBox

    @property
    def text(self) -> str:
        """문단의 전체 텍스트"""
        return "\n".join(line.text for line in self.lines)


@dataclass
class TextBlock:
    """텍스트 블록 레벨 정보"""
    id: int
    paragraphs: List[Paragraph]
    bbox: BBox

    @property
    def text(self) -> str:
        """블록의 전체 텍스트"""
        return "\n\n".join(para.text for para in self.paragraphs)


@dataclass
class LayoutInfo:
    """전체 레이아웃 정보 (Tesseract PSM 3 결과)"""
    blocks: List[TextBlock]

    @property
    def num_blocks(self) -> int:
        return len(self.blocks)

    @property
    def num_paragraphs(self) -> int:
        return sum(len(block.paragraphs) for block in self.blocks)

    @property
    def num_lines(self) -> int:
        return sum(
            len(para.lines)
            for block in self.blocks
            for para in block.paragraphs
        )


@dataclass
class TextRegion:
    """특정 영역의 텍스트 추출 결과"""
    text: str
    bbox: BBox
    confidence: float


@dataclass
class TableDetection:
    """표 감지 및 추출 결과"""
    rows: int
    cols: int
    cells: List[List[str]]  # 2D 배열 (cells[row][col])
    bbox: BBox

    def to_markdown(self) -> str:
        """Markdown 표 형식으로 변환"""
        if not self.cells:
            return ""

        lines = []

        # 헤더
        header = "| " + " | ".join(self.cells[0]) + " |"
        lines.append(header)

        # 구분선
        separator = "| " + " | ".join(["---"] * self.cols) + " |"
        lines.append(separator)

        # 데이터 행
        for row in self.cells[1:]:
            row_str = "| " + " | ".join(row) + " |"
            lines.append(row_str)

        return "\n".join(lines)

    def to_csv(self) -> str:
        """CSV 형식으로 변환"""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(self.cells)
        return output.getvalue()


@dataclass
class OCRResult:
    """Tesseract OCR 추출 결과"""
    text: str
    confidence: float  # 0.0 ~ 1.0
    layout_info: LayoutInfo
    language: str
    processing_time: float  # 초

    def to_dict(self) -> dict:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            "text": self.text,
            "confidence": self.confidence,
            "language": self.language,
            "processing_time": self.processing_time,
            "num_blocks": self.layout_info.num_blocks,
            "num_paragraphs": self.layout_info.num_paragraphs,
            "num_lines": self.layout_info.num_lines,
        }


@dataclass
class AnalysisResult:
    """하이브리드 분석 결과 (Vision + OCR)"""
    vision_context: str  # Claude Vision이 분석한 시각적 맥락
    ocr_text: str  # Tesseract가 추출한 정밀 텍스트
    confidence: float
    mode: str  # "vision", "ocr", "hybrid"
    metadata: dict = field(default_factory=dict)


# --- Hybrid Pipeline 신규 모델 (기존 코드 아래 append) ---


@dataclass
class UIElement:
    """UI 요소 (Layer 1 그래픽 / Layer 2 텍스트)"""
    element_type: str       # "text" | "graphic"
    bbox: BBox
    semantic_label: str = ""
    confidence: float = 1.0
    layer: int = 1
    marker_id: int = 0
    text_content: str = ""


@dataclass
class HybridAnalysisResult:
    """3-Layer Hybrid Pipeline 분석 결과"""
    elements: List[UIElement]
    annotated_image_path: Optional[str] = None
    processing_time: float = 0.0
    layer_stats: dict = field(default_factory=dict)
    mode: str = "coords"
