"""
lib.ocr.som_annotator - Set-of-Mark (SoM) 이미지 어노테이션

번호 마커를 이미지에 삽입하여 Vision LLM이 요소를 식별하도록 도움.
좌표 직접 요청 없이 시맨틱 레이블만 획득 (SoM 원칙).
"""
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from .models import UIElement

logger = logging.getLogger(__name__)


class SoMAnnotator:
    """
    Set-of-Mark(SoM) 프롬프팅 기반 시맨틱 레이블러.

    Layer 3 역할: Layer 1+2에서 감지된 요소에 번호 마커를 삽입하고
    Vision LLM에 SoM 프롬프트를 전달하여 시맨틱 레이블을 획득한다.
    좌표 추정을 LLM에 절대 요청하지 않는다.
    """

    MARKER_COLOR = (255, 0, 0)
    BOX_COLOR = (255, 0, 0)
    FONT_SCALE = 0.5
    THICKNESS = 1

    def __init__(
        self,
        tmp_dir: Optional[str] = None,
        api_timeout: int = 20,
        vision_client=None,
    ):
        self.tmp_dir = Path(tmp_dir) if tmp_dir else Path(tempfile.gettempdir()) / "ocr_som"
        self.api_timeout = api_timeout
        self._vision_client = vision_client

    def annotate(
        self,
        image: Image.Image,
        elements: List[UIElement],
    ) -> Tuple[Image.Image, Dict[int, UIElement]]:
        """각 요소에 번호 마커 삽입 → annotated_image와 {marker_id: UIElement} 반환."""
        img_cv = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        mapping: Dict[int, UIElement] = {}

        for i, elem in enumerate(elements):
            marker_id = i + 1
            elem.marker_id = marker_id
            mapping[marker_id] = elem

            b = elem.bbox
            cv2.rectangle(
                img_cv,
                (b.x, b.y),
                (b.x + b.width, b.y + b.height),
                self.BOX_COLOR,
                self.THICKNESS,
            )
            cv2.putText(
                img_cv,
                str(marker_id),
                (b.x, max(b.y - 3, 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                self.FONT_SCALE,
                self.MARKER_COLOR,
                self.THICKNESS,
            )

        result_image = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
        return result_image, mapping

    def save_annotated(self, image: Image.Image, output_path: str) -> str:
        """어노테이션된 이미지 저장, 저장 경로 반환."""
        image.save(output_path)
        return output_path

    def label_with_vision(
        self,
        annotated_image_path: Path,
        elements: List[UIElement],
    ) -> List[UIElement]:
        """
        Vision LLM에 SoM 프롬프트 전달 → 시맨틱 레이블 획득.
        API 실패 시 semantic_label='unknown' 처리.
        """
        if self._vision_client is None:
            raise ValueError(
                "vision_client is required for SoM labeling. "
                "Provide via lib/ai_auth/ or pass client directly."
            )

        try:
            import base64
            import json

            with open(annotated_image_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")

            prompt = (
                "이 이미지에 빨간 번호 마커가 표시된 UI 요소들이 있습니다.\n"
                "각 번호의 요소가 무엇인지 시맨틱 레이블을 부여하세요.\n"
                "의미만 분류하세요.\n\n"
                'JSON 형식으로만 응답하세요: '
                '{"1": "submit_button", "2": "search_input", ...}'
            )

            message = self._vision_client.messages.create(
                model="claude-opus-4-6",
                max_tokens=1024,
                timeout=self.api_timeout,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_data,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )

            label_map = json.loads(message.content[0].text)
            for elem in elements:
                label = label_map.get(str(elem.marker_id))
                if label:
                    elem.semantic_label = label
                    elem.layer = 3

        except Exception as e:
            logger.warning("SoM vision labeling failed: %s", e)

        return elements

    def cleanup(self) -> None:
        """tmp_dir 내 어노테이션 임시 이미지 정리."""
        if self.tmp_dir.exists():
            for f in self.tmp_dir.glob("annotated_*.png"):
                try:
                    f.unlink()
                except Exception as e:
                    logger.warning("Failed to delete temp file %s: %s", f, e)
