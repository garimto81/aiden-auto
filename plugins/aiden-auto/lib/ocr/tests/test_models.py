"""
lib.ocr.models 테스트

데이터 모델의 메서드 및 property 검증.
"""

from lib.ocr.models import (
    BBox, Word, Line, Paragraph, TextBlock, LayoutInfo,
    TableDetection, OCRResult, AnalysisResult
)


class TestBBox:
    """BBox 클래스 테스트"""

    def test_area(self):
        """면적 계산 테스트"""
        bbox = BBox(x=10, y=20, width=100, height=50)
        assert bbox.area() == 5000

    def test_contains_true(self):
        """다른 BBox를 포함하는 경우"""
        outer = BBox(x=0, y=0, width=100, height=100)
        inner = BBox(x=10, y=10, width=50, height=50)

        assert outer.contains(inner) is True

    def test_contains_false(self):
        """다른 BBox를 포함하지 않는 경우"""
        bbox1 = BBox(x=0, y=0, width=50, height=50)
        bbox2 = BBox(x=60, y=60, width=50, height=50)

        assert bbox1.contains(bbox2) is False

    def test_contains_partial_overlap(self):
        """부분적으로 겹치는 경우 (포함하지 않음)"""
        bbox1 = BBox(x=0, y=0, width=100, height=100)
        bbox2 = BBox(x=50, y=50, width=100, height=100)

        assert bbox1.contains(bbox2) is False


class TestWord:
    """Word 클래스 테스트"""

    def test_word_creation(self):
        """Word 객체 생성"""
        bbox = BBox(x=10, y=20, width=30, height=15)
        word = Word(text="Hello", bbox=bbox, confidence=0.95)

        assert word.text == "Hello"
        assert word.bbox == bbox
        assert word.confidence == 0.95


class TestLine:
    """Line 클래스 테스트"""

    def test_text_property(self):
        """줄의 전체 텍스트 property"""
        bbox1 = BBox(x=10, y=10, width=30, height=15)
        bbox2 = BBox(x=50, y=10, width=30, height=15)

        words = [
            Word(text="Hello", bbox=bbox1, confidence=0.95),
            Word(text="World", bbox=bbox2, confidence=0.92),
        ]

        line_bbox = BBox(x=10, y=10, width=70, height=15)
        line = Line(words=words, bbox=line_bbox)

        assert line.text == "Hello World"


class TestParagraph:
    """Paragraph 클래스 테스트"""

    def test_text_property(self):
        """문단의 전체 텍스트 property"""
        bbox1 = BBox(x=10, y=10, width=30, height=15)
        bbox2 = BBox(x=50, y=10, width=30, height=15)
        bbox3 = BBox(x=10, y=30, width=30, height=15)

        line1 = Line(
            words=[Word(text="Hello", bbox=bbox1, confidence=0.95)],
            bbox=bbox1
        )
        line2 = Line(
            words=[Word(text="World", bbox=bbox2, confidence=0.92)],
            bbox=bbox2
        )

        para_bbox = BBox(x=10, y=10, width=70, height=35)
        para = Paragraph(lines=[line1, line2], bbox=para_bbox)

        # 줄 단위로 개행
        assert para.text == "Hello\nWorld"


class TestTextBlock:
    """TextBlock 클래스 테스트"""

    def test_text_property(self):
        """블록의 전체 텍스트 property"""
        bbox1 = BBox(x=10, y=10, width=30, height=15)
        bbox2 = BBox(x=10, y=30, width=30, height=15)

        line1 = Line(words=[Word(text="Para1", bbox=bbox1, confidence=0.95)], bbox=bbox1)
        line2 = Line(words=[Word(text="Para2", bbox=bbox2, confidence=0.92)], bbox=bbox2)

        para1 = Paragraph(lines=[line1], bbox=bbox1)
        para2 = Paragraph(lines=[line2], bbox=bbox2)

        block_bbox = BBox(x=10, y=10, width=30, height=35)
        block = TextBlock(id=1, paragraphs=[para1, para2], bbox=block_bbox)

        # 문단 단위로 2개 개행
        assert block.text == "Para1\n\nPara2"


class TestLayoutInfo:
    """LayoutInfo 클래스 테스트"""

    def test_num_blocks(self):
        """블록 수 계산"""
        bbox = BBox(x=0, y=0, width=100, height=100)
        block1 = TextBlock(id=1, paragraphs=[], bbox=bbox)
        block2 = TextBlock(id=2, paragraphs=[], bbox=bbox)

        layout = LayoutInfo(blocks=[block1, block2])

        assert layout.num_blocks == 2

    def test_num_paragraphs(self):
        """문단 수 계산"""
        bbox = BBox(x=0, y=0, width=100, height=100)
        para1 = Paragraph(lines=[], bbox=bbox)
        para2 = Paragraph(lines=[], bbox=bbox)
        para3 = Paragraph(lines=[], bbox=bbox)

        block1 = TextBlock(id=1, paragraphs=[para1, para2], bbox=bbox)
        block2 = TextBlock(id=2, paragraphs=[para3], bbox=bbox)

        layout = LayoutInfo(blocks=[block1, block2])

        assert layout.num_paragraphs == 3

    def test_num_lines(self):
        """줄 수 계산"""
        bbox = BBox(x=0, y=0, width=100, height=100)
        line1 = Line(words=[], bbox=bbox)
        line2 = Line(words=[], bbox=bbox)
        line3 = Line(words=[], bbox=bbox)

        para1 = Paragraph(lines=[line1, line2], bbox=bbox)
        para2 = Paragraph(lines=[line3], bbox=bbox)

        block = TextBlock(id=1, paragraphs=[para1, para2], bbox=bbox)
        layout = LayoutInfo(blocks=[block])

        assert layout.num_lines == 3


class TestTableDetection:
    """TableDetection 클래스 테스트"""

    def test_to_markdown(self):
        """Markdown 표 형식 변환"""
        cells = [
            ["Name", "Age"],
            ["Alice", "30"],
            ["Bob", "25"],
        ]

        bbox = BBox(x=0, y=0, width=200, height=100)
        table = TableDetection(rows=3, cols=2, cells=cells, bbox=bbox)

        markdown = table.to_markdown()

        # 헤더
        assert "| Name | Age |" in markdown
        # 구분선
        assert "| --- | --- |" in markdown
        # 데이터 행
        assert "| Alice | 30 |" in markdown
        assert "| Bob | 25 |" in markdown

    def test_to_csv(self):
        """CSV 형식 변환"""
        cells = [
            ["Name", "Age"],
            ["Alice", "30"],
            ["Bob", "25"],
        ]

        bbox = BBox(x=0, y=0, width=200, height=100)
        table = TableDetection(rows=3, cols=2, cells=cells, bbox=bbox)

        csv = table.to_csv()

        assert "Name,Age" in csv
        assert "Alice,30" in csv
        assert "Bob,25" in csv

    def test_empty_cells(self):
        """빈 셀 리스트 처리"""
        bbox = BBox(x=0, y=0, width=200, height=100)
        table = TableDetection(rows=0, cols=0, cells=[], bbox=bbox)

        assert table.to_markdown() == ""


class TestOCRResult:
    """OCRResult 클래스 테스트"""

    def test_to_dict(self):
        """딕셔너리 변환 (JSON 직렬화)"""
        bbox = BBox(x=0, y=0, width=100, height=100)
        line = Line(words=[], bbox=bbox)
        para = Paragraph(lines=[line], bbox=bbox)
        block = TextBlock(id=1, paragraphs=[para], bbox=bbox)
        layout = LayoutInfo(blocks=[block])

        result = OCRResult(
            text="Hello World",
            confidence=0.95,
            layout_info=layout,
            language="eng",
            processing_time=0.5
        )

        result_dict = result.to_dict()

        assert result_dict["text"] == "Hello World"
        assert result_dict["confidence"] == 0.95
        assert result_dict["language"] == "eng"
        assert result_dict["processing_time"] == 0.5
        assert result_dict["num_blocks"] == 1
        assert result_dict["num_paragraphs"] == 1
        assert result_dict["num_lines"] == 1


class TestAnalysisResult:
    """AnalysisResult 클래스 테스트"""

    def test_creation(self):
        """기본 생성 테스트"""
        result = AnalysisResult(
            vision_context="Image shows a document",
            ocr_text="Document text",
            confidence=0.9,
            mode="hybrid",
            metadata={"source": "test"}
        )

        assert result.vision_context == "Image shows a document"
        assert result.ocr_text == "Document text"
        assert result.confidence == 0.9
        assert result.mode == "hybrid"
        assert result.metadata["source"] == "test"

    def test_default_metadata(self):
        """metadata 기본값 테스트"""
        result = AnalysisResult(
            vision_context="",
            ocr_text="Text",
            confidence=0.8,
            mode="ocr"
        )

        assert result.metadata == {}
