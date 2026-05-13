"""
lib.ocr.preprocessor 테스트

이미지 전처리 파이프라인 검증. cv2를 mock하여 의존성 최소화.
"""

import pytest
from PIL import Image
from unittest.mock import patch
import numpy as np

from lib.ocr.preprocessor import ImagePreprocessor


class TestGrayscale:
    """grayscale 메서드 테스트"""

    def test_grayscale_conversion(self, sample_image):
        """RGB → L 변환 확인"""
        gray = ImagePreprocessor.grayscale(sample_image)

        assert gray.mode == "L", "흑백 모드가 아님"


class TestThreshold:
    """threshold 메서드 테스트 (cv2 mock)"""

    @patch("lib.ocr.preprocessor.cv2")
    def test_threshold_otsu(self, mock_cv2, sample_image):
        """Otsu 이진화 테스트"""
        # cv2.threshold mock
        mock_cv2.cvtColor.return_value = np.zeros((100, 200), dtype=np.uint8)
        mock_cv2.threshold.return_value = (127, np.ones((100, 200), dtype=np.uint8) * 255)
        mock_cv2.COLOR_RGB2BGR = 4
        mock_cv2.COLOR_BGR2GRAY = 6
        mock_cv2.THRESH_BINARY = 0
        mock_cv2.THRESH_OTSU = 8

        binary = ImagePreprocessor.threshold(sample_image, method="otsu")

        # cv2.threshold가 호출되었는지 확인
        mock_cv2.threshold.assert_called_once()
        assert isinstance(binary, Image.Image)

    @patch("lib.ocr.preprocessor.cv2")
    def test_threshold_adaptive_gaussian(self, mock_cv2, sample_image):
        """Adaptive Gaussian 이진화 테스트"""
        mock_cv2.cvtColor.return_value = np.zeros((100, 200), dtype=np.uint8)
        mock_cv2.adaptiveThreshold.return_value = np.ones((100, 200), dtype=np.uint8) * 255
        mock_cv2.COLOR_RGB2BGR = 4
        mock_cv2.COLOR_BGR2GRAY = 6
        mock_cv2.ADAPTIVE_THRESH_GAUSSIAN_C = 1
        mock_cv2.THRESH_BINARY = 0

        binary = ImagePreprocessor.threshold(sample_image, method="adaptive_gaussian")

        mock_cv2.adaptiveThreshold.assert_called_once()
        assert isinstance(binary, Image.Image)

    @patch("lib.ocr.preprocessor.cv2")
    def test_threshold_adaptive_mean(self, mock_cv2, sample_image):
        """Adaptive Mean 이진화 테스트"""
        mock_cv2.cvtColor.return_value = np.zeros((100, 200), dtype=np.uint8)
        mock_cv2.adaptiveThreshold.return_value = np.ones((100, 200), dtype=np.uint8) * 255
        mock_cv2.COLOR_RGB2BGR = 4
        mock_cv2.COLOR_BGR2GRAY = 6
        mock_cv2.ADAPTIVE_THRESH_MEAN_C = 0
        mock_cv2.THRESH_BINARY = 0

        binary = ImagePreprocessor.threshold(sample_image, method="adaptive_mean")

        mock_cv2.adaptiveThreshold.assert_called_once()

    def test_threshold_invalid_method(self, sample_image):
        """잘못된 method → ValueError"""
        with pytest.raises(ValueError, match="Unknown threshold method"):
            ImagePreprocessor.threshold(sample_image, method="invalid")


class TestDenoise:
    """denoise 메서드 테스트"""

    def test_denoise_gaussian(self, sample_image):
        """Gaussian Blur 테스트 (PIL 사용, mock 불필요)"""
        denoised = ImagePreprocessor.denoise(sample_image, method="gaussian")

        assert isinstance(denoised, Image.Image)

    @patch("lib.ocr.preprocessor.cv2")
    def test_denoise_median(self, mock_cv2, sample_image):
        """Median Filter 테스트"""
        mock_cv2.cvtColor.return_value = np.zeros((100, 200, 3), dtype=np.uint8)
        mock_cv2.medianBlur.return_value = np.zeros((100, 200, 3), dtype=np.uint8)
        mock_cv2.COLOR_RGB2BGR = 4
        mock_cv2.COLOR_BGR2RGB = 5

        denoised = ImagePreprocessor.denoise(sample_image, method="median")

        mock_cv2.medianBlur.assert_called_once()

    @patch("lib.ocr.preprocessor.cv2")
    def test_denoise_bilateral(self, mock_cv2, sample_image):
        """Bilateral Filter 테스트"""
        mock_cv2.cvtColor.return_value = np.zeros((100, 200, 3), dtype=np.uint8)
        mock_cv2.bilateralFilter.return_value = np.zeros((100, 200, 3), dtype=np.uint8)
        mock_cv2.COLOR_RGB2BGR = 4
        mock_cv2.COLOR_BGR2RGB = 5

        denoised = ImagePreprocessor.denoise(sample_image, method="bilateral")

        mock_cv2.bilateralFilter.assert_called_once()

    def test_denoise_invalid_method(self, sample_image):
        """잘못된 method → ValueError"""
        with pytest.raises(ValueError, match="Unknown denoise method"):
            ImagePreprocessor.denoise(sample_image, method="invalid")


class TestSharpen:
    """sharpen 메서드 테스트"""

    def test_sharpen_default_strength(self, sample_image):
        """기본 강도 (1.0) 테스트"""
        sharpened = ImagePreprocessor.sharpen(sample_image)

        assert isinstance(sharpened, Image.Image)

    def test_sharpen_custom_strength(self, sample_image):
        """커스텀 강도 (0.5) 테스트"""
        sharpened = ImagePreprocessor.sharpen(sample_image, strength=0.5)

        assert isinstance(sharpened, Image.Image)


class TestPipeline:
    """pipeline 메서드 테스트"""

    def test_pipeline_single_step(self, sample_image):
        """단일 단계 파이프라인"""
        preprocessor = ImagePreprocessor()
        result = preprocessor.pipeline(sample_image, steps=["grayscale"])

        assert result.mode == "L"

    @patch("lib.ocr.preprocessor.cv2")
    def test_pipeline_multiple_steps(self, mock_cv2, sample_image):
        """다단계 파이프라인 (grayscale → denoise → threshold)"""
        # cv2 mock 설정
        mock_cv2.cvtColor.return_value = np.zeros((100, 200), dtype=np.uint8)
        mock_cv2.adaptiveThreshold.return_value = np.ones((100, 200), dtype=np.uint8) * 255
        mock_cv2.COLOR_RGB2BGR = 4
        mock_cv2.COLOR_BGR2GRAY = 6
        mock_cv2.ADAPTIVE_THRESH_GAUSSIAN_C = 1
        mock_cv2.THRESH_BINARY = 0

        preprocessor = ImagePreprocessor()
        result = preprocessor.pipeline(
            sample_image,
            steps=["grayscale", "denoise", "threshold"]
        )

        assert isinstance(result, Image.Image)

    def test_pipeline_with_kwargs(self, sample_image):
        """파이프라인 kwargs 전달 테스트"""
        preprocessor = ImagePreprocessor()
        result = preprocessor.pipeline(
            sample_image,
            steps=["grayscale", "sharpen"],
            sharpen_strength=1.5
        )

        assert isinstance(result, Image.Image)

    def test_pipeline_invalid_step(self, sample_image):
        """잘못된 step → ValueError"""
        preprocessor = ImagePreprocessor()

        with pytest.raises(ValueError, match="Unknown preprocessing step"):
            preprocessor.pipeline(sample_image, steps=["invalid_step"])


class TestGetPreset:
    """get_preset 클래스 메서드 테스트"""

    def test_get_preset_document(self):
        """document 프리셋"""
        steps = ImagePreprocessor.get_preset("document")

        assert steps == ["grayscale", "deskew", "threshold"]

    def test_get_preset_photo(self):
        """photo 프리셋"""
        steps = ImagePreprocessor.get_preset("photo")

        assert steps == ["denoise", "sharpen", "grayscale", "threshold"]

    def test_get_preset_screenshot(self):
        """screenshot 프리셋"""
        steps = ImagePreprocessor.get_preset("screenshot")

        assert steps == ["grayscale", "threshold"]

    def test_get_preset_handwriting(self):
        """handwriting 프리셋"""
        steps = ImagePreprocessor.get_preset("handwriting")

        assert steps == ["grayscale", "denoise", "deskew", "sharpen"]

    def test_get_preset_table(self):
        """table 프리셋"""
        steps = ImagePreprocessor.get_preset("table")

        assert steps == ["grayscale", "threshold", "denoise"]

    def test_get_preset_invalid(self):
        """잘못된 프리셋 → ValueError"""
        with pytest.raises(ValueError, match="Unknown preset"):
            ImagePreprocessor.get_preset("invalid_preset")
