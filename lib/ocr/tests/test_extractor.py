"""
lib.ocr.extractor 테스트

pytesseract를 mock하여 Tesseract 미설치 환경에서도 테스트 가능.
"""

import pytest
import numpy as np
from unittest.mock import patch

from lib.ocr.extractor import OCRExtractor
from lib.ocr.models import BBox, OCRResult
from lib.ocr.errors import TesseractNotFoundError, ImageLoadError, OCRError


class TestOCRExtractorInit:
    """OCRExtractor 초기화 테스트"""

    def test_init_success(self, tmp_image_path, mock_pytesseract):
        """정상 초기화"""
        with patch("lib.ocr.extractor.pytesseract", mock_pytesseract):
            extractor = OCRExtractor(tmp_image_path, lang="eng")

            assert extractor.image_path == tmp_image_path
            assert extractor.lang == "eng"
            assert extractor._image is not None

    def test_init_with_tesseract_cmd(self, tmp_image_path, mock_pytesseract):
        """tesseract_cmd 파라미터 지정"""
        with patch("lib.ocr.extractor.pytesseract", mock_pytesseract):
            extractor = OCRExtractor(
                tmp_image_path,
                lang="eng",
                tesseract_cmd="/custom/tesseract"
            )

            # tesseract_cmd가 설정되었는지 확인
            assert mock_pytesseract.pytesseract.tesseract_cmd == "/custom/tesseract"

    def test_init_image_not_found(self, mock_pytesseract):
        """존재하지 않는 이미지 → ImageLoadError"""
        with patch("lib.ocr.extractor.pytesseract", mock_pytesseract):
            with pytest.raises(ImageLoadError, match="Failed to load image"):
                OCRExtractor("nonexistent.png")

    def test_init_tesseract_not_installed(self, tmp_image_path, mock_tesseract_not_installed):
        """Tesseract 미설치 → TesseractNotFoundError"""
        with patch("lib.ocr.extractor.pytesseract", mock_tesseract_not_installed):
            with patch("shutil.which", return_value=None):
                with patch("pathlib.Path.exists", return_value=False):
                    with pytest.raises(TesseractNotFoundError, match="not installed"):
                        OCRExtractor(tmp_image_path)


class TestAutoDetectTesseract:
    """_auto_detect_tesseract 메서드 테스트"""

    def test_detect_from_path(self, tmp_image_path, mock_pytesseract):
        """PATH에서 tesseract 탐색"""
        with patch("lib.ocr.extractor.pytesseract", mock_pytesseract):
            with patch("shutil.which", return_value="/usr/bin/tesseract"):
                extractor = OCRExtractor(tmp_image_path)

                # tesseract_cmd가 PATH에서 발견된 경로로 설정되었는지 확인
                assert mock_pytesseract.pytesseract.tesseract_cmd == "/usr/bin/tesseract"

    @patch("lib.ocr.extractor.Path.exists")
    def test_detect_from_default_paths(self, mock_exists, tmp_image_path, mock_pytesseract):
        """Windows 기본 경로에서 탐색"""
        with patch("lib.ocr.extractor.pytesseract", mock_pytesseract):
            with patch("shutil.which", return_value=None):
                # 첫 번째 기본 경로 존재
                mock_exists.side_effect = lambda: True

                extractor = OCRExtractor(tmp_image_path)

                # tesseract_cmd가 설정되었는지 확인 (실제 경로는 mock에 따라 다름)
                assert mock_pytesseract.pytesseract.tesseract_cmd is not None


class TestExtractText:
    """extract_text 메서드 테스트"""

    def test_extract_text_basic(self, tmp_image_path, mock_pytesseract):
        """기본 텍스트 추출"""
        with patch("lib.ocr.extractor.pytesseract", mock_pytesseract):
            extractor = OCRExtractor(tmp_image_path, lang="eng")
            result = extractor.extract_text(preprocess=False)

            assert isinstance(result, OCRResult)
            assert result.text == "Mocked OCR Text"
            assert 0.0 <= result.confidence <= 1.0
            assert result.language == "eng"
            assert result.processing_time >= 0

    def test_extract_text_with_preprocess(self, tmp_image_path, mock_pytesseract):
        """전처리 활성화"""
        with patch("lib.ocr.extractor.pytesseract", mock_pytesseract):
            extractor = OCRExtractor(tmp_image_path, lang="eng")
            result = extractor.extract_text(preprocess=True)

            assert isinstance(result, OCRResult)
            # 전처리가 적용되었는지 확인 (이미지가 변경되었는지)
            # mock이므로 실제 전처리 효과는 확인 불가, 에러 없이 실행되는지만 확인

    def test_extract_text_custom_config(self, tmp_image_path, mock_pytesseract):
        """커스텀 Tesseract config"""
        with patch("lib.ocr.extractor.pytesseract", mock_pytesseract):
            extractor = OCRExtractor(tmp_image_path, lang="eng")
            result = extractor.extract_text(config="--psm 6")

            # image_to_string이 호출될 때 config가 전달되었는지 확인
            mock_pytesseract.image_to_string.assert_called()
            call_kwargs = mock_pytesseract.image_to_string.call_args[1]
            assert call_kwargs["config"] == "--psm 6"


class TestExtractRegions:
    """extract_regions 메서드 테스트"""

    def test_extract_regions_single_bbox(self, tmp_image_path, mock_pytesseract):
        """단일 bbox 영역 추출"""
        with patch("lib.ocr.extractor.pytesseract", mock_pytesseract):
            extractor = OCRExtractor(tmp_image_path, lang="eng")
            boxes = [BBox(x=10, y=10, width=50, height=20)]

            regions = extractor.extract_regions(boxes, preprocess=False)

            assert len(regions) == 1
            assert regions[0].text == "Mocked OCR Text"
            assert regions[0].bbox == boxes[0]
            assert 0.0 <= regions[0].confidence <= 1.0

    def test_extract_regions_multiple_bbox(self, tmp_image_path, mock_pytesseract):
        """다중 bbox 영역 추출"""
        with patch("lib.ocr.extractor.pytesseract", mock_pytesseract):
            extractor = OCRExtractor(tmp_image_path, lang="eng")
            boxes = [
                BBox(x=10, y=10, width=50, height=20),
                BBox(x=70, y=10, width=50, height=20),
            ]

            regions = extractor.extract_regions(boxes)

            assert len(regions) == 2


class TestCalculateConfidence:
    """_calculate_confidence 메서드 테스트"""

    def test_calculate_confidence_normal(self, tmp_image_path, mock_pytesseract):
        """정상 신뢰도 계산"""
        with patch("lib.ocr.extractor.pytesseract", mock_pytesseract):
            extractor = OCRExtractor(tmp_image_path, lang="eng")

            data = {
                "conf": [95, 90, 85]  # 평균 90
            }

            confidence = extractor._calculate_confidence(data)

            # 0-100 → 0.0-1.0 변환
            assert confidence == pytest.approx(0.9, abs=0.01)

    def test_calculate_confidence_with_negative_one(self, tmp_image_path, mock_pytesseract):
        """conf=-1 (빈 영역) 제외"""
        with patch("lib.ocr.extractor.pytesseract", mock_pytesseract):
            extractor = OCRExtractor(tmp_image_path, lang="eng")

            data = {
                "conf": [95, -1, 90, -1, 85]  # -1 제외, 평균 90
            }

            confidence = extractor._calculate_confidence(data)

            assert confidence == pytest.approx(0.9, abs=0.01)

    def test_calculate_confidence_empty(self, tmp_image_path, mock_pytesseract):
        """빈 데이터 → 0.0"""
        with patch("lib.ocr.extractor.pytesseract", mock_pytesseract):
            extractor = OCRExtractor(tmp_image_path, lang="eng")

            data = {"conf": []}

            confidence = extractor._calculate_confidence(data)

            assert confidence == 0.0


class TestVerifyTesseract:
    """_verify_tesseract 메서드 테스트"""

    def test_verify_tesseract_installed(self, tmp_image_path, mock_pytesseract):
        """Tesseract 설치 확인 (정상)"""
        with patch("lib.ocr.extractor.pytesseract", mock_pytesseract):
            # 초기화 시 자동 검증됨
            extractor = OCRExtractor(tmp_image_path, lang="eng")

            # 예외 없이 초기화 완료
            assert extractor is not None

    def test_verify_tesseract_missing_language(self, tmp_image_path, mock_missing_language):
        """언어팩 누락 → OCRError"""
        with patch("lib.ocr.extractor.pytesseract", mock_missing_language):
            with patch("shutil.which", return_value="/usr/bin/tesseract"):
                with pytest.raises(OCRError, match="Missing language packs"):
                    OCRExtractor(tmp_image_path, lang="kor+eng")


class TestGetDefaultConfig:
    """_get_default_config 메서드 테스트"""

    def test_default_config(self, tmp_image_path, mock_pytesseract):
        """기본 config 문자열"""
        with patch("lib.ocr.extractor.pytesseract", mock_pytesseract):
            extractor = OCRExtractor(tmp_image_path, lang="eng")
            config = extractor._get_default_config()

            assert "--psm 3" in config
            assert "--oem 3" in config


class TestExtractLayoutInfo:
    """_extract_layout_info 메서드 테스트"""

    def test_extract_layout_info(self, tmp_image_path, mock_pytesseract):
        """레이아웃 정보 추출"""
        with patch("lib.ocr.extractor.pytesseract", mock_pytesseract):
            extractor = OCRExtractor(tmp_image_path, lang="eng")

            # mock_pytesseract의 기본 데이터 사용
            data = mock_pytesseract.image_to_data.return_value

            layout = extractor._extract_layout_info(data)

            assert layout.num_blocks > 0
            assert layout.num_lines > 0


class TestDetectTables:
    """detect_tables 메서드 테스트 (간단한 케이스)"""

    def test_detect_tables_no_lines(self, tmp_image_path, mock_pytesseract):
        """선이 없는 경우 → 빈 리스트"""
        with patch("lib.ocr.extractor.pytesseract", mock_pytesseract):
            extractor = OCRExtractor(tmp_image_path, lang="eng")

            with patch("cv2.cvtColor") as mock_cvt, \
                 patch("cv2.Canny") as mock_canny, \
                 patch("cv2.HoughLinesP", return_value=None):
                mock_cvt.return_value = np.zeros((100, 100), dtype=np.uint8)
                mock_canny.return_value = np.zeros((100, 100), dtype=np.uint8)

                tables = extractor.detect_tables()
                assert tables == []
