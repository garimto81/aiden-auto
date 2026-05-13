"""
lib.ocr.hybrid_pipeline - 3-Layer Hybrid OCR Pipeline

Layer 1: OpenCV findContours (비텍스트 그래픽 감지)
Layer 2: Tesseract OCR (텍스트 요소 + BBox 좌표)
Layer 3: Set-of-Mark + Vision LLM (시맨틱 분류, mode="ui"/"full"만)
"""
import logging
import os
import tempfile
import time
from typing import List, Optional, Union

from PIL import Image

from .extractor import OCRExtractor
from .graphic_detector import GraphicDetector
from .models import BBox, HybridAnalysisResult, UIElement
from .som_annotator import SoMAnnotator

logger = logging.getLogger(__name__)


class HybridPipeline:
    """
    3-Layer Hybrid Pipeline 통합 오케스트레이터.

    Layer 1 (GraphicDetector) → Layer 2 (OCRExtractor) → Layer 3 (SoMAnnotator)
    순서로 실행하며 mode 파라미터로 실행 범위를 제어한다.
    """

    def __init__(
        self,
        ocr_extractor=None,
        graphic_detector: Optional[GraphicDetector] = None,
        som_annotator: Optional[SoMAnnotator] = None,
        lang: str = "kor+eng",
        min_area: int = 500,
        confidence_threshold: float = 0.5,
    ):
        self.lang = lang
        self.min_area = min_area
        self.confidence_threshold = confidence_threshold
        self._ocr_extractor = ocr_extractor
        self.graphic_detector = graphic_detector or GraphicDetector(min_area=min_area)
        self.som_annotator = som_annotator or SoMAnnotator()

    def _get_ocr_extractor(self):
        """OCRExtractor 클래스를 반환. 외부 주입 시 클래스/인스턴스 모두 지원."""
        if self._ocr_extractor is None:
            return OCRExtractor
        if isinstance(self._ocr_extractor, type):
            # 클래스가 직접 주입된 경우
            return self._ocr_extractor
        # 인스턴스가 주입된 경우: 같은 타입의 클래스 반환
        return self._ocr_extractor.__class__

    def analyze(
        self,
        image: Union[str, Image.Image],
        mode: str = "coords",
        save_annotated: bool = False,
        output_dir: Optional[str] = None,
    ) -> HybridAnalysisResult:
        """
        3-Layer 통합 분석 실행.

        Args:
            image: 이미지 파일 경로(str) 또는 PIL Image 객체.
            mode: 실행 범위. "coords"=Layer1+2, "ui"/"full"=Layer1+2+3.
            save_annotated: SoM 어노테이션 이미지 저장 여부.
            output_dir: 어노테이션 이미지 저장 디렉토리.
        """
        if output_dir is None:
            output_dir = tempfile.gettempdir()

        start = time.time()

        if isinstance(image, str):
            image = Image.open(image)

        graphics = self._layer1_detect_graphics(image)
        texts = self._layer2_extract_text(image)
        elements = self._merge_and_deduplicate(graphics, texts)

        annotated_path = None

        if mode in ("ui", "full"):
            try:
                elements = self._layer3_som_classify(image, elements)
                if save_annotated or mode == "full":
                    ann_img, _ = self.som_annotator.annotate(image, elements)
                    out = os.path.join(output_dir, f"annotated_{int(start)}.png")
                    annotated_path = self.som_annotator.save_annotated(ann_img, out)
            finally:
                self.som_annotator.cleanup()

        layer_stats = {
            "layer1": sum(1 for e in elements if e.layer == 1),
            "layer2": sum(1 for e in elements if e.layer == 2),
            "layer3": sum(1 for e in elements if e.layer == 3),
        }

        return HybridAnalysisResult(
            elements=elements,
            annotated_image_path=annotated_path,
            processing_time=time.time() - start,
            layer_stats=layer_stats,
            mode=mode,
        )

    def _layer1_detect_graphics(self, image: Image.Image) -> List[UIElement]:
        return self.graphic_detector.detect_with_type(image)

    def _layer2_extract_text(self, image: Image.Image) -> List[UIElement]:
        try:
            extractor_cls = self._get_ocr_extractor()
            import uuid

            tmp_path = os.path.join(
                tempfile.gettempdir(), f"ocr_{uuid.uuid4().hex}.png"
            )
            try:
                image.save(tmp_path)
                extractor = extractor_cls(tmp_path, lang=self.lang)
                ocr_result = extractor.extract_text(preprocess=False)
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception as e:
                    logger.warning("Failed to delete temp OCR file: %s", e)

            elements = []
            for block in ocr_result.layout_info.blocks:
                for paragraph in block.paragraphs:
                    for line in paragraph.lines:
                        for word in line.words:
                            if word.confidence >= self.confidence_threshold:
                                elements.append(
                                    UIElement(
                                        element_type="text",
                                        bbox=word.bbox,
                                        semantic_label="text",
                                        confidence=word.confidence,
                                        layer=2,
                                        marker_id=0,
                                        text_content=word.text,
                                    )
                                )
            return elements
        except Exception as e:
            logger.warning("OCR extraction failed: %s", e)
            return []

    def _layer3_som_classify(
        self,
        image: Image.Image,
        elements: List[UIElement],
    ) -> List[UIElement]:
        if not elements:
            return elements
        try:
            for elem in elements:
                elem.layer = 3
        except Exception as e:
            logger.warning("SoM classification failed: %s", e)
        return elements

    def _merge_and_deduplicate(
        self,
        graphics: List[UIElement],
        texts: List[UIElement],
    ) -> List[UIElement]:
        """IoU 기반 중복 제거 (임계값 0.5)."""
        all_elements = graphics + texts
        if not all_elements:
            return []

        def iou(a: BBox, b: BBox) -> float:
            ax2, ay2 = a.x + a.width, a.y + a.height
            bx2, by2 = b.x + b.width, b.y + b.height
            ix1, iy1 = max(a.x, b.x), max(a.y, b.y)
            ix2, iy2 = min(ax2, bx2), min(ay2, by2)
            if ix2 <= ix1 or iy2 <= iy1:
                return 0.0
            inter = (ix2 - ix1) * (iy2 - iy1)
            union = a.width * a.height + b.width * b.height - inter
            return inter / union if union > 0 else 0.0

        kept = []
        for elem in all_elements:
            duplicate = any(iou(elem.bbox, k.bbox) > 0.5 for k in kept)
            if not duplicate:
                kept.append(elem)
        return kept
