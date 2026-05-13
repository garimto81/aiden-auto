"""
lib.ocr.graphic_detector - OpenCV 기반 비텍스트 그래픽 요소 감지

cv2.findContours()로 UI 요소 감지, BBox 좌표 반환
"""
from typing import List, Optional

import cv2
import numpy as np
from PIL import Image

from .models import BBox, UIElement


class GraphicDetector:
    """
    OpenCV cv2.findContours() 기반 비텍스트 UI 요소 감지기.

    Layer 1 역할: 이미지 내 버튼, 아이콘, 이미지 블록, 입력 필드 등
    비텍스트 요소의 픽셀 BBox를 정밀하게 추출한다.
    """

    def __init__(
        self,
        min_area: int = 500,
        max_area: Optional[int] = None,
        overlap_threshold: float = 0.5,
    ):
        self.min_area = min_area
        self.max_area = max_area
        self.overlap_threshold = overlap_threshold

    def detect(self, image: Image.Image) -> List[BBox]:
        """비텍스트 요소 BBox 리스트 반환."""
        img_cv = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
        _, binary = cv2.threshold(
            img_cv, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        bboxes = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_area:
                continue
            if self.max_area is not None and area > self.max_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            bboxes.append(BBox(x=x, y=y, width=w, height=h))
        return bboxes

    def detect_with_type(self, image: Image.Image) -> List[UIElement]:
        """detect() 결과를 UIElement(element_type='graphic', layer=1)로 변환."""
        bboxes = self.detect(image)
        return [
            UIElement(element_type="graphic", bbox=b, layer=1, marker_id=i + 1)
            for i, b in enumerate(bboxes)
        ]

    def filter_overlapping(
        self,
        graphic_elements: List[UIElement],
        text_elements: List[UIElement],
    ) -> List[UIElement]:
        """텍스트 BBox와 IoU overlap_threshold 초과 중복 그래픽 요소 제거."""
        result = []
        for g in graphic_elements:
            overlaps = any(
                self._compute_iou(g.bbox, t.bbox) > self.overlap_threshold
                for t in text_elements
            )
            if not overlaps:
                result.append(g)
        return result

    def _compute_iou(self, bbox1: BBox, bbox2: BBox) -> float:
        """두 BBox 간 IoU(Intersection over Union) 계산."""
        ix1 = max(bbox1.x, bbox2.x)
        iy1 = max(bbox1.y, bbox2.y)
        ix2 = min(bbox1.x + bbox1.width, bbox2.x + bbox2.width)
        iy2 = min(bbox1.y + bbox1.height, bbox2.y + bbox2.height)

        if ix2 <= ix1 or iy2 <= iy1:
            return 0.0

        inter = (ix2 - ix1) * (iy2 - iy1)
        union = bbox1.area() + bbox2.area() - inter
        return inter / union if union > 0 else 0.0
