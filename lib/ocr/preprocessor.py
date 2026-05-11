"""
lib.ocr.preprocessor - 이미지 전처리 파이프라인

OCR 정확도를 높이기 위한 이미지 전처리 단계 제공.
OpenCV와 Pillow 조합 사용.
"""

from PIL import Image, ImageFilter, ImageEnhance
import cv2
import numpy as np
from typing import List, Literal


PreprocessStep = Literal["grayscale", "threshold", "deskew", "denoise", "sharpen"]


class ImagePreprocessor:
    """
    이미지 전처리 파이프라인

    OCR 정확도를 높이기 위한 이미지 전처리 단계 제공.
    OpenCV와 Pillow 조합 사용.

    Example:
        >>> preprocessor = ImagePreprocessor()
        >>> image = Image.open("noisy.jpg")
        >>> clean = preprocessor.pipeline(image, ["grayscale", "denoise", "threshold"])
    """

    @staticmethod
    def grayscale(image: Image.Image) -> Image.Image:
        """
        흑백 변환 (RGB → Grayscale)

        Args:
            image: PIL 이미지 객체

        Returns:
            Image.Image: 흑백 변환된 이미지
        """
        return image.convert("L")

    @staticmethod
    def threshold(
        image: Image.Image,
        method: Literal["otsu", "adaptive_gaussian", "adaptive_mean"] = "adaptive_gaussian"
    ) -> Image.Image:
        """
        이진화 (흑백 → 0 또는 255)

        Args:
            image: PIL 이미지 (흑백 권장)
            method: 이진화 방법
                - "otsu": Otsu's method (전역 임계값)
                - "adaptive_gaussian": Adaptive Gaussian Threshold (지역 임계값)
                - "adaptive_mean": Adaptive Mean Threshold

        Returns:
            Image.Image: 이진화된 이미지

        Example:
            >>> gray = ImagePreprocessor.grayscale(image)
            >>> binary = ImagePreprocessor.threshold(gray, method="adaptive_gaussian")
        """
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        if method == "otsu":
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        elif method == "adaptive_gaussian":
            binary = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=11,
                C=2
            )
        elif method == "adaptive_mean":
            binary = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_MEAN_C,
                cv2.THRESH_BINARY,
                blockSize=11,
                C=2
            )
        else:
            raise ValueError(f"Unknown threshold method: {method}")

        return Image.fromarray(binary)

    @staticmethod
    def deskew(image: Image.Image, angle_threshold: float = 0.5) -> Image.Image:
        """
        기울기 보정 (Skew correction)

        Hough Line Transform으로 텍스트 줄 기울기 감지 → 회전 보정

        Args:
            image: PIL 이미지
            angle_threshold: 보정 최소 각도 (도). 이 값 미만이면 보정 스킵

        Returns:
            Image.Image: 기울기 보정된 이미지
        """
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        # Canny edge detection
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)

        # Hough Line Transform
        lines = cv2.HoughLines(edges, 1, np.pi/180, 200)

        if lines is None:
            return image

        # 각도 계산 (중앙값)
        angles = []
        for rho, theta in lines[:, 0]:
            angle = (theta - np.pi / 2) * 180 / np.pi
            angles.append(angle)

        median_angle = np.median(angles)

        if abs(median_angle) < angle_threshold:
            return image

        # 회전
        (h, w) = img_cv.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(
            img_cv,
            M,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )

        return Image.fromarray(cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB))

    @staticmethod
    def denoise(
        image: Image.Image,
        method: Literal["gaussian", "median", "bilateral"] = "gaussian"
    ) -> Image.Image:
        """
        노이즈 제거

        Args:
            image: PIL 이미지
            method: 노이즈 제거 방법
                - "gaussian": Gaussian Blur (빠름, 경계 흐림)
                - "median": Median Filter (Salt-and-pepper 노이즈 효과적)
                - "bilateral": Bilateral Filter (경계 보존, 느림)

        Returns:
            Image.Image: 노이즈 제거된 이미지
        """
        if method == "gaussian":
            return image.filter(ImageFilter.GaussianBlur(radius=1))

        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        if method == "median":
            denoised = cv2.medianBlur(img_cv, ksize=3)
        elif method == "bilateral":
            denoised = cv2.bilateralFilter(img_cv, d=9, sigmaColor=75, sigmaSpace=75)
        else:
            raise ValueError(f"Unknown denoise method: {method}")

        return Image.fromarray(cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB))

    @staticmethod
    def sharpen(image: Image.Image, strength: float = 1.0) -> Image.Image:
        """
        샤프닝 (선명도 향상)

        Args:
            image: PIL 이미지
            strength: 샤프닝 강도 (0.0 ~ 2.0)

        Returns:
            Image.Image: 샤프닝된 이미지
        """
        enhancer = ImageEnhance.Sharpness(image)
        return enhancer.enhance(1.0 + strength)

    def pipeline(
        self,
        image: Image.Image,
        steps: List[PreprocessStep],
        **kwargs
    ) -> Image.Image:
        """
        전처리 파이프라인 실행

        Args:
            image: PIL 이미지
            steps: 전처리 단계 리스트 (순서대로 실행)
            **kwargs: 각 단계별 파라미터 (예: threshold_method="otsu")

        Returns:
            Image.Image: 전처리된 이미지

        Example:
            >>> preprocessor = ImagePreprocessor()
            >>> result = preprocessor.pipeline(
            ...     image,
            ...     steps=["grayscale", "denoise", "threshold"],
            ...     threshold_method="adaptive_gaussian"
            ... )
        """
        current = image

        for step in steps:
            if step == "grayscale":
                current = self.grayscale(current)
            elif step == "threshold":
                method = kwargs.get("threshold_method", "adaptive_gaussian")
                current = self.threshold(current, method=method)
            elif step == "deskew":
                angle_threshold = kwargs.get("deskew_angle_threshold", 0.5)
                current = self.deskew(current, angle_threshold=angle_threshold)
            elif step == "denoise":
                method = kwargs.get("denoise_method", "gaussian")
                current = self.denoise(current, method=method)
            elif step == "sharpen":
                strength = kwargs.get("sharpen_strength", 1.0)
                current = self.sharpen(current, strength=strength)
            else:
                raise ValueError(f"Unknown preprocessing step: {step}")

        return current

    @classmethod
    def get_preset(cls, preset_name: str) -> List[PreprocessStep]:
        """
        이미지 유형별 최적 전처리 프리셋

        Args:
            preset_name: 프리셋 이름
                - "document": 문서 스캔 (흑백, 이진화)
                - "photo": 사진 텍스트 (노이즈 제거, 샤프닝)
                - "screenshot": 스크린샷 (기본 전처리)
                - "handwriting": 손글씨 (샤프닝, 기울기 보정)
                - "table": 표 (선 감지 최적화)

        Returns:
            List[PreprocessStep]: 전처리 단계 리스트

        Example:
            >>> steps = ImagePreprocessor.get_preset("document")
            >>> image = preprocessor.pipeline(image, steps)
        """
        presets = {
            "document": ["grayscale", "deskew", "threshold"],
            "photo": ["denoise", "sharpen", "grayscale", "threshold"],
            "screenshot": ["grayscale", "threshold"],
            "handwriting": ["grayscale", "denoise", "deskew", "sharpen"],
            "table": ["grayscale", "threshold", "denoise"],
        }

        if preset_name not in presets:
            raise ValueError(
                f"Unknown preset: {preset_name}. "
                f"Available: {list(presets.keys())}"
            )

        return presets[preset_name]
