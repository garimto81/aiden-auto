"""
pytest fixtures for OCR tests

Tesseract 미설치 환경에서도 테스트 가능하도록 mock fixtures 제공.
"""

import pytest
from PIL import Image, ImageDraw
from unittest.mock import MagicMock, patch


@pytest.fixture
def sample_image():
    """간단한 텍스트 이미지 생성 (ImageDraw 사용)"""
    # 200x100 흰색 배경 이미지
    image = Image.new("RGB", (200, 100), color="white")
    draw = ImageDraw.Draw(image)

    # 텍스트 그리기 (기본 폰트)
    draw.text((10, 40), "Hello World", fill="black")

    return image


@pytest.fixture
def sample_korean_image():
    """한글 포함 이미지"""
    image = Image.new("RGB", (300, 100), color="white")
    draw = ImageDraw.Draw(image)

    # 한글 텍스트 (유니코드)
    draw.text((10, 40), "안녕하세요", fill="black")

    return image


@pytest.fixture
def sample_table_image():
    """표 이미지 (가로/세로선 + 셀 텍스트)"""
    # 400x300 흰색 배경
    image = Image.new("RGB", (400, 300), color="white")
    draw = ImageDraw.Draw(image)

    # 표 그리드 (3행 2열)
    # 가로선
    for y in [50, 150, 250]:
        draw.line([(50, y), (350, y)], fill="black", width=2)

    # 세로선
    for x in [50, 200, 350]:
        draw.line([(x, 50), (x, 250)], fill="black", width=2)

    # 셀 텍스트
    cells = [
        (70, 80, "Name"),
        (220, 80, "Age"),
        (70, 180, "Alice"),
        (220, 180, "30"),
        (70, 280, "Bob"),
        (220, 280, "25"),
    ]

    for x, y, text in cells:
        draw.text((x, y), text, fill="black")

    return image


@pytest.fixture
def tmp_image_path(tmp_path, sample_image):
    """임시 파일 경로 fixture"""
    image_path = tmp_path / "test_image.png"
    sample_image.save(image_path)
    return image_path


@pytest.fixture
def mock_pytesseract():
    """pytesseract를 mock하여 Tesseract 미설치 환경 테스트"""
    with patch("lib.ocr.extractor.pytesseract") as mock_pyt:
        # get_tesseract_version mock
        mock_pyt.get_tesseract_version.return_value = "5.3.0"

        # get_languages mock
        mock_pyt.get_languages.return_value = ["kor", "eng", "osd"]

        # image_to_string mock
        mock_pyt.image_to_string.return_value = "Mocked OCR Text"

        # image_to_data mock
        mock_pyt.image_to_data.return_value = {
            "text": ["Mocked", "OCR", "Text"],
            "conf": [95, 90, 92],
            "left": [10, 50, 90],
            "top": [10, 10, 10],
            "width": [30, 30, 30],
            "height": [20, 20, 20],
            "block_num": [1, 1, 1],
            "par_num": [1, 1, 1],
            "line_num": [1, 1, 1],
            "word_num": [1, 2, 3],
        }

        # Output enum mock
        mock_pyt.Output = MagicMock()
        mock_pyt.Output.DICT = "dict"

        # tesseract_cmd path mock
        mock_pyt.pytesseract = MagicMock()
        mock_pyt.pytesseract.tesseract_cmd = "tesseract"

        yield mock_pyt


@pytest.fixture
def mock_tesseract_not_installed():
    """Tesseract 미설치 상황 mock"""
    with patch("lib.ocr.extractor.pytesseract") as mock_pyt:
        mock_pyt.get_tesseract_version.side_effect = FileNotFoundError("tesseract not found")
        yield mock_pyt


@pytest.fixture
def mock_missing_language():
    """언어팩 누락 상황 mock"""
    with patch("lib.ocr.extractor.pytesseract") as mock_pyt:
        mock_pyt.get_tesseract_version.return_value = "5.3.0"
        mock_pyt.get_languages.return_value = ["eng", "osd"]  # kor 누락
        yield mock_pyt


@pytest.fixture
def mock_shutil_which():
    """shutil.which를 mock (Tesseract 경로 탐색)"""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/tesseract"
        yield mock_which
