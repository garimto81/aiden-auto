from typing import List, Optional, Dict, Any
from pathlib import Path
from PIL import Image
import pytesseract
import numpy as np
from .models import OCRResult, TextRegion, TableDetection, LayoutInfo, BBox, TextBlock, Paragraph, Line, Word
from .preprocessor import ImagePreprocessor
from .errors import OCRError, TesseractNotFoundError, ImageLoadError


class OCRExtractor:
    """
    Tesseract OCR wrapper 클래스

    이미지에서 텍스트를 추출하는 핵심 클래스. pytesseract를 래핑하여
    전처리, 영역 기반 추출, 표 감지, 레이아웃 분석 기능 제공.

    Attributes:
        image_path (Path): 처리할 이미지 파일 경로
        lang (str): Tesseract 언어 코드 (예: "kor+eng")
        _image (Image.Image): 로드된 PIL 이미지 객체
        _preprocessor (ImagePreprocessor): 이미지 전처리 파이프라인

    Example:
        >>> extractor = OCRExtractor("invoice.jpg", lang="kor+eng")
        >>> result = extractor.extract_text(preprocess=True)
        >>> print(result.text)
        >>> print(f"Confidence: {result.confidence}")
    """

    def __init__(
        self,
        image_path: str | Path,
        lang: str = "kor+eng",
        tesseract_cmd: Optional[str] = None
    ):
        """
        OCRExtractor 초기화

        Args:
            image_path: 처리할 이미지 파일 경로
            lang: Tesseract 언어 코드 (기본값: "kor+eng")
            tesseract_cmd: Tesseract 실행 파일 경로 (None이면 자동 탐색)

        Raises:
            ImageLoadError: 이미지 로드 실패
            TesseractNotFoundError: Tesseract 바이너리 미발견
        """
        self.image_path = Path(image_path)
        self.lang = lang
        self._preprocessor = ImagePreprocessor()

        # Tesseract 경로 설정
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        else:
            self._auto_detect_tesseract()

        # Tesseract 설치 검증
        self._verify_tesseract()

        # 이미지 로드
        try:
            self._image = Image.open(self.image_path)
        except Exception as e:
            raise ImageLoadError(f"Failed to load image: {e}")

    def extract_text(
        self,
        preprocess: bool = True,
        config: Optional[str] = None
    ) -> OCRResult:
        """
        전체 이미지에서 텍스트 추출

        Args:
            preprocess: 전처리 활성화 여부 (기본값: True)
            config: Tesseract 설정 문자열 (예: "--psm 6")

        Returns:
            OCRResult: 추출된 텍스트, 신뢰도, 레이아웃 정보

        Example:
            >>> result = extractor.extract_text(preprocess=True)
            >>> if result.confidence > 0.8:
            ...     print(result.text)
        """
        import time
        start_time = time.time()

        # 전처리
        image = self._image.copy()
        if preprocess:
            image = self._preprocessor.pipeline(
                image,
                steps=["grayscale", "threshold", "denoise"]
            )

        # Tesseract 설정
        tesseract_config = config or self._get_default_config()

        # 텍스트 추출
        try:
            text = pytesseract.image_to_string(
                image,
                lang=self.lang,
                config=tesseract_config
            )

            # 신뢰도 정보 추출 (pytesseract.image_to_data 사용)
            data = pytesseract.image_to_data(
                image,
                lang=self.lang,
                output_type=pytesseract.Output.DICT
            )
            confidence = self._calculate_confidence(data)

            # 레이아웃 정보 추출
            layout_info = self._extract_layout_info(data)

        except Exception as e:
            raise OCRError(f"OCR extraction failed: {e}")

        processing_time = time.time() - start_time

        return OCRResult(
            text=text.strip(),
            confidence=confidence,
            layout_info=layout_info,
            language=self.lang,
            processing_time=processing_time
        )

    def extract_regions(
        self,
        boxes: List[BBox],
        preprocess: bool = True
    ) -> List[TextRegion]:
        """
        특정 영역(bbox)에서만 텍스트 추출

        Args:
            boxes: 추출할 영역 리스트 [(x, y, width, height), ...]
            preprocess: 전처리 활성화 여부

        Returns:
            List[TextRegion]: 각 영역의 텍스트, bbox, 신뢰도

        Example:
            >>> boxes = [BBox(x=100, y=50, width=200, height=30)]
            >>> regions = extractor.extract_regions(boxes)
            >>> for region in regions:
            ...     print(f"{region.text} (conf: {region.confidence})")
        """
        image = self._image.copy()
        if preprocess:
            image = self._preprocessor.pipeline(
                image,
                steps=["grayscale", "threshold"]
            )

        regions = []
        for bbox in boxes:
            # 영역 크롭
            cropped = image.crop((
                bbox.x,
                bbox.y,
                bbox.x + bbox.width,
                bbox.y + bbox.height
            ))

            # OCR 수행
            text = pytesseract.image_to_string(cropped, lang=self.lang)
            data = pytesseract.image_to_data(
                cropped,
                lang=self.lang,
                output_type=pytesseract.Output.DICT
            )
            confidence = self._calculate_confidence(data)

            regions.append(TextRegion(
                text=text.strip(),
                bbox=bbox,
                confidence=confidence
            ))

        return regions

    def detect_tables(
        self,
        preprocess: bool = True
    ) -> List[TableDetection]:
        """
        표 영역 자동 감지 및 텍스트 추출

        OpenCV Hough Line Transform으로 가로/세로선 감지 →
        교차점 기반 셀 영역 추출 → 각 셀 OCR 수행

        Args:
            preprocess: 전처리 활성화 여부

        Returns:
            List[TableDetection]: 감지된 표 리스트 (행/열/셀 데이터/bbox)

        Example:
            >>> tables = extractor.detect_tables()
            >>> for table in tables:
            ...     print(f"Table: {table.rows}x{table.cols}")
            ...     for row in table.cells:
            ...         print(" | ".join(row))
        """
        import cv2

        # 이미지 전처리
        image = self._image.copy()
        if preprocess:
            image = self._preprocessor.pipeline(
                image,
                steps=["grayscale", "threshold"]
            )

        # PIL → OpenCV
        image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)

        # 선 감지 (Hough Line Transform)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi/180,
            threshold=100,
            minLineLength=100,
            maxLineGap=10
        )

        if lines is None:
            return []

        # 가로선/세로선 분리
        h_lines, v_lines = self._separate_lines(lines)

        # 표 영역 감지
        tables = self._detect_table_regions(h_lines, v_lines)

        # 각 표의 셀 OCR 수행
        table_results = []
        for table_bbox, cell_boxes in tables:
            cells = self._extract_table_cells(image, cell_boxes)
            rows, cols = self._infer_table_dimensions(cell_boxes)

            table_results.append(TableDetection(
                rows=rows,
                cols=cols,
                cells=cells,
                bbox=table_bbox
            ))

        return table_results

    def get_layout_info(self) -> LayoutInfo:
        """
        레이아웃 분석 (텍스트 블록, 열, 문단 구조)

        Tesseract의 PSM(Page Segmentation Mode) 3 사용하여
        블록, 문단, 줄, 단어 레벨 위계 추출

        Returns:
            LayoutInfo: 텍스트 블록, 문단, 줄, 단어 위치 정보

        Example:
            >>> layout = extractor.get_layout_info()
            >>> for block in layout.blocks:
            ...     print(f"Block {block.id}: {len(block.paragraphs)} paragraphs")
        """
        data = pytesseract.image_to_data(
            self._image,
            lang=self.lang,
            config="--psm 3",  # Fully automatic page segmentation
            output_type=pytesseract.Output.DICT
        )

        return self._parse_layout_data(data)

    # Private 메서드

    def _auto_detect_tesseract(self) -> None:
        """Tesseract 실행 파일 자동 탐색 (PATH → 기본 경로 → 환경변수)"""
        import shutil
        import os

        # 1. PATH에서 탐색
        tesseract_path = shutil.which("tesseract")
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            return

        # 2. Windows 기본 경로
        default_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            Path.home() / "scoop/shims/tesseract.exe"
        ]
        for path in default_paths:
            if Path(path).exists():
                pytesseract.pytesseract.tesseract_cmd = str(path)
                return

        # 3. 환경변수 TESSERACT_CMD
        env_path = os.getenv("TESSERACT_CMD")
        if env_path and Path(env_path).exists():
            pytesseract.pytesseract.tesseract_cmd = env_path
            return

    def _verify_tesseract(self) -> None:
        """Tesseract 설치 및 언어팩 검증"""
        try:
            version = pytesseract.get_tesseract_version()
        except Exception:
            raise TesseractNotFoundError(
                "Tesseract not installed. "
                "Install via: scoop install tesseract"
            )

        # 언어팩 검증
        available_langs = pytesseract.get_languages()
        required_langs = self.lang.split("+")
        missing_langs = [l for l in required_langs if l not in available_langs]

        if missing_langs:
            raise OCRError(
                f"Missing language packs: {missing_langs}. "
                f"Available: {available_langs}"
            )

    def _get_default_config(self) -> str:
        """기본 Tesseract 설정 문자열 반환"""
        # PSM 3: Fully automatic page segmentation (default)
        # OEM 3: Default, based on what is available
        return "--psm 3 --oem 3"

    def _calculate_confidence(self, data: Dict[str, Any]) -> float:
        """
        pytesseract.image_to_data의 confidence 필드로부터
        평균 신뢰도 계산 (0.0 ~ 1.0)
        """
        confidences = [
            float(conf) for conf in data["conf"]
            if conf != -1  # -1은 빈 영역
        ]
        if not confidences:
            return 0.0
        return sum(confidences) / len(confidences) / 100.0

    def _extract_layout_info(self, data: Dict[str, Any]) -> LayoutInfo:
        """pytesseract.image_to_data로부터 레이아웃 정보 추출"""
        # block_num, par_num, line_num, word_num 계층 파싱
        blocks_dict: Dict[int, Dict] = {}

        for i in range(len(data["text"])):
            block_num = data["block_num"][i]
            par_num = data["par_num"][i]
            line_num = data["line_num"][i]
            word_num = data["word_num"][i]
            text = data["text"][i]
            conf = data["conf"][i]

            # 빈 텍스트 스킵
            if not text.strip():
                continue

            # BBox 생성
            x = data["left"][i]
            y = data["top"][i]
            w = data["width"][i]
            h = data["height"][i]
            bbox = BBox(x=x, y=y, width=w, height=h)
            confidence = float(conf) / 100.0 if conf != -1 else 0.0

            # 단어 객체 생성
            word = Word(text=text, bbox=bbox, confidence=confidence)

            # 계층 구조 빌드
            if block_num not in blocks_dict:
                blocks_dict[block_num] = {
                    "paragraphs": {},
                    "bbox": bbox
                }

            block = blocks_dict[block_num]

            # bbox 확장
            current_bbox = block["bbox"]
            min_x = min(current_bbox.x, x)
            min_y = min(current_bbox.y, y)
            max_x = max(current_bbox.x + current_bbox.width, x + w)
            max_y = max(current_bbox.y + current_bbox.height, y + h)
            block["bbox"] = BBox(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y)

            if par_num not in block["paragraphs"]:
                block["paragraphs"][par_num] = {
                    "lines": {},
                    "bbox": bbox
                }

            paragraph = block["paragraphs"][par_num]

            # paragraph bbox 확장
            current_bbox = paragraph["bbox"]
            min_x = min(current_bbox.x, x)
            min_y = min(current_bbox.y, y)
            max_x = max(current_bbox.x + current_bbox.width, x + w)
            max_y = max(current_bbox.y + current_bbox.height, y + h)
            paragraph["bbox"] = BBox(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y)

            if line_num not in paragraph["lines"]:
                paragraph["lines"][line_num] = {
                    "words": [],
                    "bbox": bbox
                }

            line = paragraph["lines"][line_num]

            # line bbox 확장
            current_bbox = line["bbox"]
            min_x = min(current_bbox.x, x)
            min_y = min(current_bbox.y, y)
            max_x = max(current_bbox.x + current_bbox.width, x + w)
            max_y = max(current_bbox.y + current_bbox.height, y + h)
            line["bbox"] = BBox(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y)

            line["words"].append(word)

        # 딕셔너리 → 객체 변환
        blocks = []
        for block_id, block_data in blocks_dict.items():
            paragraphs = []
            for par_data in block_data["paragraphs"].values():
                lines = []
                for line_data in par_data["lines"].values():
                    lines.append(Line(words=line_data["words"], bbox=line_data["bbox"]))
                paragraphs.append(Paragraph(lines=lines, bbox=par_data["bbox"]))
            blocks.append(TextBlock(id=block_id, paragraphs=paragraphs, bbox=block_data["bbox"]))

        return LayoutInfo(blocks=blocks)

    def _parse_layout_data(self, data: Dict[str, Any]) -> LayoutInfo:
        """레이아웃 데이터 파싱 (get_layout_info 헬퍼)"""
        return self._extract_layout_info(data)

    def _separate_lines(
        self,
        lines: np.ndarray
    ) -> tuple[List[np.ndarray], List[np.ndarray]]:
        """Hough Line Transform 결과에서 가로선/세로선 분리"""
        h_lines = []
        v_lines = []

        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi

            # 가로선: -10° ~ +10°
            if -10 < angle < 10:
                h_lines.append(line)
            # 세로선: 80° ~ 100°
            elif 80 < abs(angle) < 100:
                v_lines.append(line)

        return h_lines, v_lines

    def _detect_table_regions(
        self,
        h_lines: List[np.ndarray],
        v_lines: List[np.ndarray]
    ) -> List[tuple[BBox, List[BBox]]]:
        """가로선/세로선 교차점으로 표 영역 및 셀 영역 감지"""
        if not h_lines or not v_lines:
            return []

        # 표 전체 bbox 계산
        all_x = [line[0][0] for line in v_lines] + [line[0][2] for line in v_lines]
        all_y = [line[0][1] for line in h_lines] + [line[0][3] for line in h_lines]

        table_bbox = BBox(
            x=min(all_x),
            y=min(all_y),
            width=max(all_x) - min(all_x),
            height=max(all_y) - min(all_y)
        )

        # 셀 bbox 계산 (h_lines x v_lines 교차점 기반)
        cell_boxes = self._compute_cell_boxes(h_lines, v_lines)

        return [(table_bbox, cell_boxes)]

    def _compute_cell_boxes(
        self,
        h_lines: List[np.ndarray],
        v_lines: List[np.ndarray]
    ) -> List[BBox]:
        """가로선/세로선 교차점으로 각 셀의 BBox 계산"""
        # 가로선과 세로선의 y, x 좌표 추출 및 정렬
        y_coords = sorted(set([line[0][1] for line in h_lines] + [line[0][3] for line in h_lines]))
        x_coords = sorted(set([line[0][0] for line in v_lines] + [line[0][2] for line in v_lines]))

        # 좌표 클러스터링 (가까운 좌표 병합)
        def cluster_coords(coords, threshold=10):
            if not coords:
                return []
            clustered = [coords[0]]
            for coord in coords[1:]:
                if coord - clustered[-1] > threshold:
                    clustered.append(coord)
            return clustered

        y_coords = cluster_coords(y_coords)
        x_coords = cluster_coords(x_coords)

        # 그리드 셀 생성
        cell_boxes = []
        for i in range(len(y_coords) - 1):
            for j in range(len(x_coords) - 1):
                x = x_coords[j]
                y = y_coords[i]
                w = x_coords[j + 1] - x
                h = y_coords[i + 1] - y

                # 최소 크기 필터 (노이즈 제거)
                if w > 20 and h > 10:
                    cell_boxes.append(BBox(x=x, y=y, width=w, height=h))

        return cell_boxes

    def _extract_table_cells(
        self,
        image: Image.Image,
        cell_boxes: List[BBox]
    ) -> List[List[str]]:
        """각 셀 영역 OCR 수행 → 2D 배열 반환"""
        if not cell_boxes:
            return []

        # 셀을 y 좌표로 그룹화 (행 단위)
        rows_dict: Dict[int, List[tuple[int, BBox, str]]] = {}

        for bbox in cell_boxes:
            # 이미지 크롭
            cropped = image.crop((
                bbox.x,
                bbox.y,
                bbox.x + bbox.width,
                bbox.y + bbox.height
            ))

            # OCR 수행
            text = pytesseract.image_to_string(cropped, lang=self.lang).strip()

            # y 좌표로 행 그룹화 (±10px 허용)
            row_key = round(bbox.y / 10) * 10
            if row_key not in rows_dict:
                rows_dict[row_key] = []
            rows_dict[row_key].append((bbox.x, bbox, text))

        # 행 정렬 및 각 행 내 셀을 x 좌표로 정렬
        sorted_rows = sorted(rows_dict.items())
        cells_2d = []

        for _, row_cells in sorted_rows:
            # x 좌표로 정렬
            sorted_cells = sorted(row_cells, key=lambda c: c[0])
            cells_2d.append([text for _, _, text in sorted_cells])

        return cells_2d

    def _infer_table_dimensions(
        self,
        cell_boxes: List[BBox]
    ) -> tuple[int, int]:
        """셀 bbox로부터 표 차원 추론 (rows, cols)"""
        if not cell_boxes:
            return (0, 0)

        # y 좌표 클러스터링으로 행 수 추정
        y_coords = [bbox.y for bbox in cell_boxes]
        y_clusters = set([round(y / 10) * 10 for y in y_coords])
        rows = len(y_clusters)

        # x 좌표 클러스터링으로 열 수 추정
        x_coords = [bbox.x for bbox in cell_boxes]
        x_clusters = set([round(x / 10) * 10 for x in x_coords])
        cols = len(x_clusters)

        return (rows, cols)
