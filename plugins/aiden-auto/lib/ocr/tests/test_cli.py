"""
lib.ocr.cli 테스트

CLI 인터페이스 검증 (argparse + 서브커맨드)
"""

from unittest.mock import patch, MagicMock
import json

from lib.ocr.cli import main
from lib.ocr.models import OCRResult, LayoutInfo, TableDetection, BBox


class TestCheckCommand:
    """check 서브커맨드 테스트"""

    @patch("lib.ocr.cli.check_installation")
    @patch("sys.argv", ["python -m lib.ocr", "check"])
    def test_check_installed(self, mock_check):
        """Tesseract 설치됨"""
        mock_check.return_value = {
            "installed": True,
            "version": "5.3.0",
            "languages": ["kor", "eng"],
            "path": "/usr/bin/tesseract"
        }

        exit_code = main()

        assert exit_code == 0
        mock_check.assert_called_once()

    @patch("lib.ocr.cli.check_installation")
    @patch("sys.argv", ["python -m lib.ocr", "check"])
    def test_check_not_installed(self, mock_check, capsys):
        """Tesseract 미설치"""
        mock_check.return_value = {
            "installed": False,
            "version": None,
            "languages": [],
            "path": None,
            "error": "tesseract not found"
        }

        exit_code = main()

        assert exit_code == 1

        # 설치 가이드 출력 확인
        captured = capsys.readouterr()
        assert "설치 방법" in captured.out
        assert "scoop install tesseract" in captured.out


class TestExtractCommand:
    """extract 서브커맨드 테스트"""

    @patch("lib.ocr.cli.OCRExtractor")
    @patch("sys.argv", ["python -m lib.ocr", "extract", "test.png"])
    def test_extract_basic(self, mock_extractor_class, tmp_image_path, capsys):
        """기본 텍스트 추출"""
        # OCRExtractor mock
        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor

        # extract_text mock
        bbox = BBox(x=0, y=0, width=100, height=50)
        layout = LayoutInfo(blocks=[])

        mock_result = OCRResult(
            text="Test OCR Result",
            confidence=0.95,
            layout_info=layout,
            language="kor+eng",
            processing_time=0.5
        )
        mock_extractor.extract_text.return_value = mock_result

        # 실제 파일 존재하도록 patch
        with patch("lib.ocr.cli.Path.exists", return_value=True):
            exit_code = main()

        assert exit_code == 0

        # 출력 확인
        captured = capsys.readouterr()
        assert "Test OCR Result" in captured.out
        assert "Confidence: 0.95" in captured.out

    @patch("lib.ocr.cli.OCRExtractor")
    @patch("sys.argv", ["python -m lib.ocr", "extract", "test.png", "--no-preprocess"])
    def test_extract_no_preprocess(self, mock_extractor_class, tmp_image_path):
        """--no-preprocess 옵션"""
        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor

        bbox = BBox(x=0, y=0, width=100, height=50)
        layout = LayoutInfo(blocks=[])
        mock_result = OCRResult(
            text="Test",
            confidence=0.9,
            layout_info=layout,
            language="kor+eng",
            processing_time=0.3
        )
        mock_extractor.extract_text.return_value = mock_result

        with patch("lib.ocr.cli.Path.exists", return_value=True):
            exit_code = main()

        # extract_text가 preprocess=False로 호출되었는지 확인
        mock_extractor.extract_text.assert_called_once()
        call_kwargs = mock_extractor.extract_text.call_args[1]
        assert call_kwargs["preprocess"] is False

    @patch("lib.ocr.cli.OCRExtractor")
    @patch("sys.argv", ["python -m lib.ocr", "extract", "test.png", "--output", "output.json"])
    def test_extract_with_output(self, mock_extractor_class, tmp_path):
        """--output 옵션 (JSON 파일 저장)"""
        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor

        bbox = BBox(x=0, y=0, width=100, height=50)
        layout = LayoutInfo(blocks=[])
        mock_result = OCRResult(
            text="Test Output",
            confidence=0.88,
            layout_info=layout,
            language="eng",
            processing_time=0.4
        )
        mock_extractor.extract_text.return_value = mock_result

        output_path = tmp_path / "output.json"

        with patch("lib.ocr.cli.Path.exists", return_value=True):
            with patch("lib.ocr.cli.Path.write_text") as mock_write:
                # sys.argv의 --output 경로를 tmp_path로 변경
                import sys
                sys.argv[-1] = str(output_path)

                exit_code = main()

        assert exit_code == 0

        # write_text가 호출되었는지 확인
        mock_write.assert_called_once()
        written_data = json.loads(mock_write.call_args[0][0])
        assert written_data["text"] == "Test Output"

    @patch("lib.ocr.cli.OCRExtractor")
    @patch("sys.argv", ["python -m lib.ocr", "extract", "test.png", "--table"])
    def test_extract_table_mode(self, mock_extractor_class, capsys):
        """--table 옵션 (표 감지)"""
        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor

        # detect_tables mock
        bbox = BBox(x=0, y=0, width=200, height=100)
        mock_table = TableDetection(
            rows=2,
            cols=2,
            cells=[["A", "B"], ["C", "D"]],
            bbox=bbox
        )
        mock_extractor.detect_tables.return_value = [mock_table]

        with patch("lib.ocr.cli.Path.exists", return_value=True):
            exit_code = main()

        assert exit_code == 0

        # Markdown 표 출력 확인
        captured = capsys.readouterr()
        assert "Table 1 (2x2)" in captured.out
        assert "| A | B |" in captured.out

    @patch("sys.argv", ["python -m lib.ocr", "extract", "nonexistent.png"])
    def test_extract_file_not_found(self, capsys):
        """존재하지 않는 파일 → 에러"""
        with patch("lib.ocr.cli.Path.exists", return_value=False):
            exit_code = main()

        assert exit_code == 1

        captured = capsys.readouterr()
        assert "Error" in captured.out
        assert "찾을 수 없음" in captured.out

    @patch("lib.ocr.cli.OCRExtractor")
    @patch("sys.argv", ["python -m lib.ocr", "extract", "test.png"])
    def test_extract_exception(self, mock_extractor_class, capsys):
        """OCR 실행 중 예외 발생"""
        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.extract_text.side_effect = Exception("OCR failed")

        with patch("lib.ocr.cli.Path.exists", return_value=True):
            exit_code = main()

        assert exit_code == 1

        captured = capsys.readouterr()
        assert "Error" in captured.out
        assert "OCR failed" in captured.out
