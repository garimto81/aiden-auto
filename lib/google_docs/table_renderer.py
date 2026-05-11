"""
네이티브 Google Docs 테이블 렌더러

마크다운 테이블을 Google Docs API의 insertTable을 사용하여
실제 테이블로 변환합니다.

2단계 렌더링 방식:
1. 테이블 구조 생성 (insertTable)
2. 문서 재조회 후 텍스트/스타일 삽입
"""

import re
from dataclasses import dataclass, field
from typing import Any

from .models import TableData


def utf16_len(text: str) -> int:
    """
    Google Docs API용 UTF-16 코드 유닛 길이 계산

    Google Docs API는 인덱스를 UTF-16 코드 유닛으로 계산합니다.
    이모지 등 서로게이트 페어 문자는 2개의 코드 유닛을 사용합니다.
    """
    return len(text.encode("utf-16-le")) // 2


@dataclass
class CellInlineStyle:
    """셀 내 인라인 스타일 정보"""

    start: int  # 셀 내 상대 위치
    end: int
    bold: bool = False
    italic: bool = False
    code: bool = False


@dataclass
class ParsedCellContent:
    """파싱된 셀 내용"""

    plain_text: str  # 마크다운 기호 제거된 텍스트
    styles: list[CellInlineStyle] = field(default_factory=list)


class NativeTableRenderer:
    """마크다운 테이블을 Google Docs 네이티브 테이블로 변환 (2단계 방식)"""

    # SKILL.md 2.5 표준 테이블 스타일
    BODY_COLOR = {"red": 0.25, "green": 0.25, "blue": 0.25}  # #404040
    HEADER_BG_COLOR = {"red": 0.90, "green": 0.90, "blue": 0.90}  # #E6E6E6
    BORDER_COLOR = {"red": 0.80, "green": 0.80, "blue": 0.80}  # #CCCCCC
    CODE_BG_COLOR = {"red": 0.949, "green": 0.949, "blue": 0.949}  # #F2F2F2
    CELL_PADDING_PT = 5  # 5pt 패딩

    # 18cm 기준 테이블 너비 (1cm ≈ 28.35pt)
    TABLE_WIDTH_PT = 510  # 18cm = 510pt

    # 컬럼 최소/최대 너비 (pt)
    MIN_COLUMN_WIDTH_PT = 30   # 최소 약 1.0cm (더 컴팩트)
    MAX_COLUMN_WIDTH_PT = 400  # 최대 약 14cm (더 넓은 단일 컬럼 허용)

    # 레거시: 컬럼 수에 따른 고정 컬럼 너비 (pt) - 동적 계산 실패 시 폴백
    COLUMN_WIDTHS = {
        1: [510],           # 1열: 18cm
        2: [255, 255],      # 2열: 9cm × 2
        3: [170, 170, 170], # 3열: 6cm × 3
        4: [127.5, 127.5, 127.5, 127.5],  # 4열: 4.5cm × 4
    }

    def _parse_cell_inline_formatting(self, text: str) -> ParsedCellContent:
        """
        셀 내용에서 인라인 마크다운 파싱

        **bold**, *italic*, `code` 등을 추출하고 plain text 반환
        """
        styles: list[CellInlineStyle] = []

        # 정규식 패턴들 (순서 중요 - 긴 패턴 먼저)
        patterns = [
            # 중첩 포맷 (bold + italic)
            (r"\*\*\*(.+?)\*\*\*", "bold_italic"),  # ***bold italic***
            (r"___(.+?)___", "bold_italic"),  # ___bold italic___
            (r"\*\*_(.+?)_\*\*", "bold_italic"),  # **_bold italic_**
            (r"__\*(.+?)\*__", "bold_italic"),  # __*bold italic*__
            (r"\*__(.+?)__\*", "bold_italic"),  # *__bold italic__*
            (r"_\*\*(.+?)\*\*_", "bold_italic"),  # _**bold italic**_
            # 단일 포맷
            (r"\*\*(.+?)\*\*", "bold"),  # **bold**
            (r"__(.+?)__", "bold"),  # __bold__
            (r"\*(.+?)\*", "italic"),  # *italic*
            (r"_(.+?)_", "italic"),  # _italic_
            (r"`([^`]+)`", "code"),  # `code`
        ]

        # 모든 매치 찾기
        all_matches = []
        for pattern, style in patterns:
            for match in re.finditer(pattern, text):
                all_matches.append((match.start(), match.end(), match.group(1), style))

        # 위치순 정렬
        all_matches.sort(key=lambda x: x[0])

        # 겹치는 매치 제거
        filtered_matches = []
        last_end = 0
        for match in all_matches:
            if match[0] >= last_end:
                filtered_matches.append(match)
                last_end = match[1]

        # plain text 생성 및 스타일 정보 수집
        plain_parts = []
        current_pos = 0
        plain_offset = 0

        for start, end, content, style in filtered_matches:
            # 이전 일반 텍스트
            if start > current_pos:
                plain_parts.append(text[current_pos:start])
                plain_offset += utf16_len(text[current_pos:start])

            # 스타일 정보 저장 (plain text 기준 위치)
            style_info = CellInlineStyle(
                start=plain_offset,
                end=plain_offset + utf16_len(content),
                bold=(style == "bold" or style == "bold_italic"),
                italic=(style == "italic" or style == "bold_italic"),
                code=(style == "code"),
            )
            styles.append(style_info)

            plain_parts.append(content)
            plain_offset += utf16_len(content)
            current_pos = end

        # 남은 텍스트
        if current_pos < len(text):
            plain_parts.append(text[current_pos:])

        plain_text = "".join(plain_parts)

        return ParsedCellContent(plain_text=plain_text, styles=styles)

    def parse_markdown_table(self, table_lines: list[str]) -> TableData:
        """
        마크다운 테이블 라인을 TableData로 파싱

        Args:
            table_lines: 테이블 마크다운 라인들

        Returns:
            TableData: 파싱된 테이블 데이터
        """
        headers = []
        rows = []
        alignments = []

        for i, line in enumerate(table_lines):
            line = line.strip()
            if not line:
                continue

            # 구분선 (---) 처리 - 정렬 정보 추출
            if "---" in line or ":-" in line or "-:" in line:
                cells = [c.strip() for c in line.strip("|").split("|")]
                for cell in cells:
                    cell = cell.strip()
                    if cell.startswith(":") and cell.endswith(":"):
                        alignments.append("center")
                    elif cell.endswith(":"):
                        alignments.append("right")
                    else:
                        alignments.append("left")
                continue

            # 일반 행 처리
            # strip("|")로 양쪽 | 제거 후 split
            # 빈 셀도 보존해야 함 (index 버그 수정)
            stripped_line = line.strip("|")
            cells = [c.strip() for c in stripped_line.split("|")]

            if not headers:
                headers = cells
            else:
                rows.append(cells)

        # 열 수 정규화
        column_count = len(headers) if headers else 0
        if column_count == 0:
            return TableData(
                headers=[], rows=[], column_count=0, row_count=0, column_alignments=[]
            )

        # 행 데이터 정규화 (열 수 맞추기)
        normalized_rows = []
        for row in rows:
            if len(row) < column_count:
                row.extend([""] * (column_count - len(row)))
            elif len(row) > column_count:
                row = row[:column_count]
            normalized_rows.append(row)

        # 정렬 정보 정규화
        if len(alignments) < column_count:
            alignments.extend(["left"] * (column_count - len(alignments)))

        return TableData(
            headers=headers,
            rows=normalized_rows,
            column_count=column_count,
            row_count=len(normalized_rows) + 1,  # 헤더 포함
            column_alignments=alignments[:column_count],
        )

    # 글자당 예상 너비 (pt) - Google Docs 기본 폰트 기준
    CHAR_WIDTH_PT_ASCII = 6.5    # ASCII 문자 (영문, 숫자, 기호)
    CHAR_WIDTH_PT_CJK = 12.0     # CJK 문자 (한글, 중국어, 일본어)

    # 한 줄 표시 임계값 (이 너비 이하면 한 줄 표시 우선)
    SINGLE_LINE_THRESHOLD_PT = 180  # 약 6.3cm

    def calculate_dynamic_column_widths(self, table_data: TableData) -> list[float]:
        """
        테이블 콘텐츠 기반 동적 컬럼 너비 계산 (Single-Line First 최적화)

        최적화 전략:
        1. 각 컬럼의 "한 줄 표시 필요 너비" 계산 (글자수 × 평균 글자폭)
        2. 한 줄에 표시 가능한 컬럼은 정확한 너비 할당
        3. 긴 텍스트 컬럼은 남은 공간에서 유연하게 분배
        4. 전체 너비는 18cm(510pt) 고정

        Args:
            table_data: 파싱된 테이블 데이터

        Returns:
            list[float]: 각 컬럼의 너비 (pt)
        """
        if table_data.column_count == 0:
            return []

        # 각 열의 최대 텍스트 너비 계산 (pt 단위)
        all_rows = [table_data.headers] + table_data.rows
        max_widths_pt = [0.0] * table_data.column_count

        for row in all_rows:
            for col_idx, cell in enumerate(row):
                if col_idx < table_data.column_count:
                    # 마크다운 기호 제거 후 너비 계산
                    parsed = self._parse_cell_inline_formatting(cell)
                    text_width = self._calculate_text_width_pt(parsed.plain_text)
                    max_widths_pt[col_idx] = max(max_widths_pt[col_idx], text_width)

        # 모든 열이 비어있으면 균등 분배
        total_width = sum(max_widths_pt)
        if total_width == 0:
            equal_width = self.TABLE_WIDTH_PT / table_data.column_count
            return [equal_width] * table_data.column_count

        # Single-Line First 최적화 적용
        widths = self._optimize_single_line_first(max_widths_pt, table_data.column_count)

        # 최소/최대 너비 제한 적용
        widths = self._apply_width_constraints(widths, table_data.column_count)

        return widths

    def _calculate_text_width_pt(self, text: str) -> float:
        """
        텍스트의 예상 표시 너비 계산 (pt 단위)

        Google Docs 기본 폰트 기준으로 ASCII와 CJK 문자를 구분하여 계산합니다.
        패딩(10pt)을 포함한 실제 필요 너비를 반환합니다.

        Args:
            text: 측정할 텍스트

        Returns:
            float: 예상 너비 (pt)
        """
        if not text:
            return 0.0

        width = 0.0
        for char in text:
            # CJK 문자 판별 (한글, 중국어, 일본어)
            if '\u4e00' <= char <= '\u9fff':  # CJK 통합 한자
                width += self.CHAR_WIDTH_PT_CJK
            elif '\uac00' <= char <= '\ud7af':  # 한글 음절
                width += self.CHAR_WIDTH_PT_CJK
            elif '\u3040' <= char <= '\u30ff':  # 히라가나/가타카나
                width += self.CHAR_WIDTH_PT_CJK
            elif '\uff00' <= char <= '\uffef':  # 전각 문자
                width += self.CHAR_WIDTH_PT_CJK
            else:
                width += self.CHAR_WIDTH_PT_ASCII

        # 셀 패딩 추가 (좌우 각 5pt)
        return width + (self.CELL_PADDING_PT * 2)

    def _optimize_single_line_first(
        self, max_widths_pt: list[float], col_count: int
    ) -> list[float]:
        """
        Single-Line First 최적화: 짧은 텍스트는 한 줄 표시 우선

        전략:
        1. 한 줄 표시 가능한 컬럼 (≤ SINGLE_LINE_THRESHOLD_PT) 식별
        2. 한 줄 컬럼에 정확한 필요 너비 할당
        3. 남은 공간을 긴 텍스트 컬럼에 비율 분배
        4. 총합이 TABLE_WIDTH_PT가 되도록 조정

        Args:
            max_widths_pt: 각 컬럼의 최대 텍스트 너비 (pt)
            col_count: 컬럼 수

        Returns:
            list[float]: 최적화된 컬럼 너비 (pt)
        """
        widths = [0.0] * col_count

        # 1. 컬럼 분류: 한 줄 표시 가능 vs 줄바꿈 필요
        single_line_cols = []  # (index, width)
        multi_line_cols = []   # (index, width)

        for i, w in enumerate(max_widths_pt):
            # 최소 너비 보장
            w = max(w, self.MIN_COLUMN_WIDTH_PT)

            if w <= self.SINGLE_LINE_THRESHOLD_PT:
                single_line_cols.append((i, w))
            else:
                multi_line_cols.append((i, w))

        # 2. 한 줄 컬럼에 정확한 너비 할당
        single_line_total = sum(w for _, w in single_line_cols)

        # 한 줄 컬럼들의 총 너비가 테이블의 70%를 초과하면 비율 축소
        max_single_line_budget = self.TABLE_WIDTH_PT * 0.7
        if single_line_total > max_single_line_budget and single_line_cols:
            scale = max_single_line_budget / single_line_total
            for i, w in single_line_cols:
                widths[i] = max(w * scale, self.MIN_COLUMN_WIDTH_PT)
            single_line_total = sum(widths[i] for i, _ in single_line_cols)
        else:
            for i, w in single_line_cols:
                widths[i] = w

        # 3. 남은 공간을 긴 텍스트 컬럼에 분배
        remaining_budget = self.TABLE_WIDTH_PT - single_line_total

        if multi_line_cols:
            multi_line_total = sum(w for _, w in multi_line_cols)

            if multi_line_total > 0:
                # 비율 기반 분배
                for i, w in multi_line_cols:
                    ratio = w / multi_line_total
                    widths[i] = max(remaining_budget * ratio, self.MIN_COLUMN_WIDTH_PT)
            else:
                # 균등 분배
                equal_share = remaining_budget / len(multi_line_cols)
                for i, _ in multi_line_cols:
                    widths[i] = max(equal_share, self.MIN_COLUMN_WIDTH_PT)

        # 4. 총합 정규화 (오차 보정)
        current_total = sum(widths)
        if abs(current_total - self.TABLE_WIDTH_PT) > 0.5:
            scale = self.TABLE_WIDTH_PT / current_total
            widths = [w * scale for w in widths]

        return widths

    def _apply_width_constraints(self, widths: list[float], col_count: int) -> list[float]:
        """
        컬럼 너비에 최소/최대 제한 적용

        총합이 TABLE_WIDTH_PT를 유지하도록 조정합니다.

        Args:
            widths: 초기 계산된 너비 리스트
            col_count: 컬럼 수

        Returns:
            list[float]: 제한이 적용된 너비 리스트
        """
        if col_count == 0:
            return []

        # 1단계: 최소/최대 제한 적용
        constrained = []
        for w in widths:
            if w < self.MIN_COLUMN_WIDTH_PT:
                constrained.append(self.MIN_COLUMN_WIDTH_PT)
            elif w > self.MAX_COLUMN_WIDTH_PT:
                constrained.append(self.MAX_COLUMN_WIDTH_PT)
            else:
                constrained.append(w)

        # 2단계: 총합이 TABLE_WIDTH_PT가 되도록 조정
        current_total = sum(constrained)
        if abs(current_total - self.TABLE_WIDTH_PT) < 0.1:
            return constrained

        # 차이를 조정 가능한 열들에 분배
        diff = self.TABLE_WIDTH_PT - current_total
        adjustable_indices = []

        for i, w in enumerate(constrained):
            # 최소/최대에 걸리지 않은 열만 조정 대상
            if w > self.MIN_COLUMN_WIDTH_PT and w < self.MAX_COLUMN_WIDTH_PT:
                adjustable_indices.append(i)

        if adjustable_indices:
            adjustment_per_col = diff / len(adjustable_indices)
            for i in adjustable_indices:
                new_width = constrained[i] + adjustment_per_col
                # 조정 후에도 제한 확인
                new_width = max(self.MIN_COLUMN_WIDTH_PT, min(self.MAX_COLUMN_WIDTH_PT, new_width))
                constrained[i] = new_width
        else:
            # 모든 열이 제한에 걸린 경우, 비율 기반 재분배
            total_constrained = sum(constrained)
            if total_constrained > 0:
                scale = self.TABLE_WIDTH_PT / total_constrained
                constrained = [w * scale for w in constrained]

        return constrained

    def render_table_structure(
        self,
        table_data: TableData,
        start_index: int,
    ) -> dict[str, Any] | None:
        """
        1단계: 테이블 구조만 생성하는 요청 반환

        Args:
            table_data: 파싱된 테이블 데이터
            start_index: 테이블 삽입 시작 인덱스

        Returns:
            dict: insertTable 요청 또는 None
        """
        if table_data.column_count == 0 or table_data.row_count == 0:
            return None

        return {
            "insertTable": {
                "rows": table_data.row_count,
                "columns": table_data.column_count,
                "location": {"index": start_index},
            }
        }

    def render_table_content(
        self,
        table_data: TableData,
        table_element: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        2단계: 실제 테이블 구조를 기반으로 텍스트/스타일 요청 생성

        Args:
            table_data: 파싱된 테이블 데이터
            table_element: Google Docs에서 조회한 실제 테이블 구조

        Returns:
            list: insertText 및 updateTextStyle 요청 리스트
        """
        requests = []

        # 테이블 구조에서 각 셀의 실제 인덱스 추출
        cell_indices = self._extract_cell_indices(table_element)

        if not cell_indices:
            return requests

        # 모든 행 데이터 수집
        all_rows = [table_data.headers] + table_data.rows

        # 셀 내용 파싱 및 삽입 준비 (역순으로 - 인덱스 시프트 방지)
        insertions = []
        for row_idx, row in enumerate(all_rows):
            for col_idx, content in enumerate(row):
                if (
                    content
                    and row_idx < len(cell_indices)
                    and col_idx < len(cell_indices[row_idx])
                ):
                    cell_start = cell_indices[row_idx][col_idx]

                    # 마크다운 파싱 (** 제거, 스타일 정보 추출)
                    parsed = self._parse_cell_inline_formatting(content)

                    insertions.append(
                        {
                            "index": cell_start,
                            "content": parsed.plain_text,  # 마크다운 기호 제거된 텍스트
                            "original": content,
                            "styles": parsed.styles,  # 인라인 스타일 정보
                            "row_idx": row_idx,
                            "col_idx": col_idx,
                        }
                    )

        # 역순 정렬 (뒤에서부터 삽입)
        insertions.sort(key=lambda x: x["index"], reverse=True)

        # 텍스트 삽입 요청
        for item in insertions:
            requests.append(
                {
                    "insertText": {
                        "location": {"index": item["index"]},
                        "text": item["content"],
                    }
                }
            )

        # 스타일 적용 (텍스트 삽입 후)
        # 주의: insertText 요청들이 먼저 실행된 후에 스타일이 적용됨

        # 테이블 시작 인덱스 (셀 스타일 적용용)
        table_start_index = table_element.get("startIndex", 0)

        # 1. 테이블 전체 셀 스타일 적용 (테두리, 패딩) - SKILL.md 2.3 표준
        table = table_element.get("table", {})
        table_rows = table.get("tableRows", [])
        for row_idx, row in enumerate(table_rows):
            cells = row.get("tableCells", [])
            for col_idx, cell in enumerate(cells):
                # 테두리 스타일 정의 (SKILL.md 2.3 표준: 1pt, #CCCCCC)
                border_style = {
                    "color": {"color": {"rgbColor": self.BORDER_COLOR}},
                    "width": {"magnitude": 1, "unit": "PT"},
                    "dashStyle": "SOLID",
                }

                # 셀 스타일 요청 생성
                cell_style: dict[str, Any] = {
                    # 패딩 5pt (SKILL.md 표준)
                    "contentAlignment": "TOP",
                    "paddingTop": {"magnitude": self.CELL_PADDING_PT, "unit": "PT"},
                    "paddingBottom": {"magnitude": self.CELL_PADDING_PT, "unit": "PT"},
                    "paddingLeft": {"magnitude": self.CELL_PADDING_PT, "unit": "PT"},
                    "paddingRight": {"magnitude": self.CELL_PADDING_PT, "unit": "PT"},
                    # 테두리 (SKILL.md 표준: 1pt, #CCCCCC)
                    "borderTop": border_style,
                    "borderBottom": border_style,
                    "borderLeft": border_style,
                    "borderRight": border_style,
                }

                # 헤더 행 배경색 (SKILL.md 표준: #E6E6E6)
                if row_idx == 0:
                    cell_style["backgroundColor"] = {
                        "color": {"rgbColor": self.HEADER_BG_COLOR}
                    }

                requests.append(
                    {
                        "updateTableCellStyle": {
                            "tableRange": {
                                "tableCellLocation": {
                                    "tableStartLocation": {"index": table_start_index},
                                    "rowIndex": row_idx,
                                    "columnIndex": col_idx,
                                },
                                "rowSpan": 1,
                                "columnSpan": 1,
                            },
                            "tableCellStyle": cell_style,
                            "fields": "contentAlignment,paddingTop,paddingBottom,paddingLeft,paddingRight,borderTop,borderBottom,borderLeft,borderRight,backgroundColor",
                        }
                    }
                )

        # NOTE: 텍스트 스타일은 render_table_text_styles()에서 별도 처리
        # (인덱스 시프트 문제 방지를 위해 별도 batchUpdate 필요)

        return requests

    def render_table_text_styles(
        self,
        table_data: TableData,
        table_element: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        3단계: 텍스트 삽입 후 텍스트 스타일 적용

        insertText 실행 후 문서를 재조회한 뒤 호출해야 합니다.
        이렇게 분리하면 인덱스 시프트 문제가 해결됩니다.

        Args:
            table_data: 파싱된 테이블 데이터
            table_element: 텍스트 삽입 후 재조회한 테이블 구조

        Returns:
            list: updateTextStyle 요청 리스트
        """
        requests = []

        # 테이블 구조에서 각 셀의 실제 인덱스 추출 (삽입 후 새 인덱스)
        cell_indices = self._extract_cell_indices(table_element)

        if not cell_indices:
            return requests

        # 모든 행 데이터 수집
        all_rows = [table_data.headers] + table_data.rows

        for row_idx, row in enumerate(all_rows):
            for col_idx, content in enumerate(row):
                if (
                    content
                    and row_idx < len(cell_indices)
                    and col_idx < len(cell_indices[row_idx])
                ):
                    cell_start = cell_indices[row_idx][col_idx]

                    # 마크다운 파싱
                    parsed = self._parse_cell_inline_formatting(content)
                    plain_text = parsed.plain_text

                    if not plain_text:
                        continue

                    # 셀 스타일: 본문 색상만 (볼드는 마크다운 **...** 문법으로만 적용)
                    requests.append(
                        {
                            "updateTextStyle": {
                                "range": {
                                    "startIndex": cell_start,
                                    "endIndex": cell_start + utf16_len(plain_text),
                                },
                                "textStyle": {
                                    "foregroundColor": {
                                        "color": {"rgbColor": self.BODY_COLOR}
                                    }
                                },
                                "fields": "foregroundColor",
                            }
                        }
                    )

                    # 마크다운 인라인 스타일 적용 (**볼드**, *이탤릭*, `코드`)
                    for style in parsed.styles:
                        style_fields = []
                        inline_style: dict[str, Any] = {}

                        if style.bold:
                            inline_style["bold"] = True
                            style_fields.append("bold")

                        if style.italic:
                            inline_style["italic"] = True
                            style_fields.append("italic")

                        if style.code:
                            inline_style["weightedFontFamily"] = {
                                "fontFamily": "Consolas",
                                "weight": 400,
                            }
                            inline_style["backgroundColor"] = {
                                "color": {"rgbColor": self.CODE_BG_COLOR}
                            }
                            style_fields.extend(
                                ["weightedFontFamily", "backgroundColor"]
                            )

                        if style_fields:
                            requests.append(
                                {
                                    "updateTextStyle": {
                                        "range": {
                                            "startIndex": cell_start + style.start,
                                            "endIndex": cell_start + style.end,
                                        },
                                        "textStyle": inline_style,
                                        "fields": ",".join(style_fields),
                                    }
                                }
                            )

        return requests

    # =========================================================================
    # 최적화된 통합 렌더링 (v2.3.2+)
    # =========================================================================

    def render_table_content_and_styles(
        self,
        table_data: TableData,
        table_element: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        최적화된 2단계 통합 렌더링: 텍스트 삽입 + 셀 스타일 + 텍스트 스타일

        기존 render_table_content() + render_table_text_styles() 통합 버전.
        단일 batchUpdate로 모든 작업을 처리하여 API 호출을 최소화합니다.

        Args:
            table_data: 파싱된 테이블 데이터
            table_element: Google Docs에서 조회한 실제 테이블 구조

        Returns:
            list: 통합된 API 요청 리스트 (insertText + updateTableCellStyle + updateTextStyle)
        """
        requests: list[dict[str, Any]] = []

        # 테이블 구조에서 각 셀의 실제 인덱스 추출
        cell_indices = self._extract_cell_indices(table_element)

        if not cell_indices:
            return requests

        # 모든 행 데이터 수집
        all_rows = [table_data.headers] + table_data.rows

        # =====================================================================
        # Phase 1: 텍스트 삽입 정보 수집 및 역순 삽입
        # =====================================================================
        insertions: list[dict[str, Any]] = []

        for row_idx, row in enumerate(all_rows):
            for col_idx, content in enumerate(row):
                if (
                    content
                    and row_idx < len(cell_indices)
                    and col_idx < len(cell_indices[row_idx])
                ):
                    cell_start = cell_indices[row_idx][col_idx]

                    # 마크다운 파싱 (** 제거, 스타일 정보 추출)
                    parsed = self._parse_cell_inline_formatting(content)

                    insertions.append(
                        {
                            "index": cell_start,
                            "content": parsed.plain_text,
                            "parsed": parsed,
                            "row_idx": row_idx,
                            "col_idx": col_idx,
                        }
                    )

        # 역순 정렬 (뒤에서부터 삽입 - 인덱스 시프트 방지)
        insertions.sort(key=lambda x: x["index"], reverse=True)

        # 텍스트 삽입 요청
        for item in insertions:
            if item["content"]:
                requests.append(
                    {
                        "insertText": {
                            "location": {"index": item["index"]},
                            "text": item["content"],
                        }
                    }
                )

        # =====================================================================
        # Phase 2: 컬럼 너비 + 셀 스타일 적용 (테두리, 패딩, 헤더 배경)
        # =====================================================================
        table_start_index = table_element.get("startIndex", 0)
        table = table_element.get("table", {})
        table_rows = table.get("tableRows", [])

        # 컬럼 너비 설정 (동적 계산 - 텍스트 길이 기반)
        col_widths = self.calculate_dynamic_column_widths(table_data)

        for col_idx, width in enumerate(col_widths):
            requests.append(
                {
                    "updateTableColumnProperties": {
                        "tableStartLocation": {"index": table_start_index},
                        "columnIndices": [col_idx],
                        "tableColumnProperties": {
                            "widthType": "FIXED_WIDTH",
                            "width": {"magnitude": width, "unit": "PT"},
                        },
                        "fields": "widthType,width",
                    }
                }
            )

        for row_idx, row in enumerate(table_rows):
            cells = row.get("tableCells", [])
            for col_idx, cell in enumerate(cells):
                # 테두리 스타일 정의 (SKILL.md 2.3 표준: 1pt, #CCCCCC)
                border_style = {
                    "color": {"color": {"rgbColor": self.BORDER_COLOR}},
                    "width": {"magnitude": 1, "unit": "PT"},
                    "dashStyle": "SOLID",
                }

                # 셀 스타일 요청 생성
                cell_style: dict[str, Any] = {
                    "contentAlignment": "TOP",
                    "paddingTop": {"magnitude": self.CELL_PADDING_PT, "unit": "PT"},
                    "paddingBottom": {"magnitude": self.CELL_PADDING_PT, "unit": "PT"},
                    "paddingLeft": {"magnitude": self.CELL_PADDING_PT, "unit": "PT"},
                    "paddingRight": {"magnitude": self.CELL_PADDING_PT, "unit": "PT"},
                    "borderTop": border_style,
                    "borderBottom": border_style,
                    "borderLeft": border_style,
                    "borderRight": border_style,
                }

                # 헤더 행 배경색 (SKILL.md 표준: #E6E6E6)
                if row_idx == 0:
                    cell_style["backgroundColor"] = {
                        "color": {"rgbColor": self.HEADER_BG_COLOR}
                    }

                requests.append(
                    {
                        "updateTableCellStyle": {
                            "tableRange": {
                                "tableCellLocation": {
                                    "tableStartLocation": {"index": table_start_index},
                                    "rowIndex": row_idx,
                                    "columnIndex": col_idx,
                                },
                                "rowSpan": 1,
                                "columnSpan": 1,
                            },
                            "tableCellStyle": cell_style,
                            "fields": "contentAlignment,paddingTop,paddingBottom,paddingLeft,paddingRight,borderTop,borderBottom,borderLeft,borderRight,backgroundColor",
                        }
                    }
                )

        # =====================================================================
        # Phase 3: 텍스트 스타일 적용 (본문 색상 + 인라인 마크다운)
        # 주의: insertText 후 인덱스가 변경되므로 시프트 계산 필요
        # =====================================================================

        # 인덱스 시프트 계산 (역순 삽입으로 인한 누적 오프셋)
        # 역순 삽입이므로, 각 셀의 원래 인덱스 이후에 삽입된 텍스트 길이만큼 시프트
        index_shifts = self._calculate_index_shifts(insertions)

        for item in insertions:
            if not item["content"]:
                continue

            original_index = item["index"]
            shift = index_shifts.get(original_index, 0)
            shifted_start = original_index + shift
            parsed = item["parsed"]
            plain_text = parsed.plain_text
            is_header = item["row_idx"] == 0

            # 셀 전체에 본문 색상 적용
            text_style: dict[str, Any] = {
                "foregroundColor": {"color": {"rgbColor": self.BODY_COLOR}}
            }
            fields = ["foregroundColor"]

            # 헤더 행은 볼드 추가
            if is_header:
                text_style["bold"] = True
                fields.append("bold")

            requests.append(
                {
                    "updateTextStyle": {
                        "range": {
                            "startIndex": shifted_start,
                            "endIndex": shifted_start + utf16_len(plain_text),
                        },
                        "textStyle": text_style,
                        "fields": ",".join(fields),
                    }
                }
            )

            # 인라인 스타일 적용 (**볼드**, *이탤릭*, `코드`)
            for style in parsed.styles:
                style_fields: list[str] = []
                inline_style: dict[str, Any] = {}

                if style.bold:
                    inline_style["bold"] = True
                    style_fields.append("bold")

                if style.italic:
                    inline_style["italic"] = True
                    style_fields.append("italic")

                if style.code:
                    inline_style["weightedFontFamily"] = {
                        "fontFamily": "Consolas",
                        "weight": 400,
                    }
                    inline_style["backgroundColor"] = {
                        "color": {"rgbColor": self.CODE_BG_COLOR}
                    }
                    style_fields.extend(["weightedFontFamily", "backgroundColor"])

                if style_fields:
                    requests.append(
                        {
                            "updateTextStyle": {
                                "range": {
                                    "startIndex": shifted_start + style.start,
                                    "endIndex": shifted_start + style.end,
                                },
                                "textStyle": inline_style,
                                "fields": ",".join(style_fields),
                            }
                        }
                    )

        return requests

    def _calculate_index_shifts(
        self, insertions: list[dict[str, Any]]
    ) -> dict[int, int]:
        """
        역순 텍스트 삽입으로 인한 인덱스 시프트 계산

        역순 삽입 시, 뒤쪽 인덱스에 삽입된 텍스트는 앞쪽 인덱스에 영향을 주지 않음.
        따라서 각 인덱스는 자신보다 앞에 있는 삽입 텍스트 길이만큼 시프트됨.

        Args:
            insertions: 역순 정렬된 삽입 정보 리스트

        Returns:
            dict: {원래_인덱스: 시프트_량}
        """
        shifts: dict[int, int] = {}

        # 역순 삽입 후 스타일 적용 시 인덱스 시프트 계산
        # 역순 삽입: 인덱스 큰 것부터 삽입 (예: 100, 80, 60, 40, 20)
        # 스타일 적용 시: 인덱스 작은 것은 큰 것들의 삽입으로 인해 밀림
        for i, item in enumerate(insertions):
            current_index = item["index"]
            shift = 0

            # 자신보다 인덱스가 작은 것들에 삽입된 텍스트 길이만큼 시프트됨
            # (역순 정렬이므로 i 이후에 있는 것들이 인덱스가 작음)
            for j in range(i + 1, len(insertions)):
                other = insertions[j]
                if other["index"] < current_index:
                    shift += utf16_len(other["content"]) if other["content"] else 0

            shifts[current_index] = shift

        return shifts

    def _extract_cell_indices(self, table_element: dict[str, Any]) -> list[list[int]]:
        """
        테이블 요소에서 각 셀의 시작 인덱스 추출

        Args:
            table_element: Google Docs 테이블 구조 요소

        Returns:
            list[list[int]]: 행/열별 셀 시작 인덱스
        """
        cell_indices = []

        table = table_element.get("table")
        if not table:
            return cell_indices

        table_rows = table.get("tableRows", [])
        for row in table_rows:
            row_indices = []
            cells = row.get("tableCells", [])
            for cell in cells:
                # 셀 내 첫 번째 문단의 시작 인덱스
                content = cell.get("content", [])
                if content:
                    first_para = content[0]
                    if "paragraph" in first_para:
                        para_start = first_para.get("startIndex", 0)
                        row_indices.append(para_start)
            cell_indices.append(row_indices)

        return cell_indices

    def get_table_end_index(self, table_element: dict[str, Any]) -> int:
        """
        테이블의 끝 인덱스 반환

        Args:
            table_element: Google Docs 테이블 구조 요소

        Returns:
            int: 테이블 끝 인덱스
        """
        return table_element.get("endIndex", 0)

    # =========================================================================
    # 레거시 메서드 (하위 호환성) - v2.4.0에서 제거 예정
    # =========================================================================

    def render(
        self,
        table_data: TableData,
        start_index: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        [DEPRECATED] 단일 batchUpdate용 테이블 렌더링

        .. deprecated:: 2.3.0
            이 메서드는 인덱스 계산 문제로 자주 실패합니다.
            대신 `render_table_structure()` + `render_table_content()`를 사용하세요.
            v2.4.0에서 제거 예정입니다.

        Warning:
            이 메서드는 더 이상 사용하지 마세요.

        Args:
            table_data: 파싱된 테이블 데이터
            start_index: 테이블 삽입 시작 인덱스

        Returns:
            tuple: (API 요청 리스트, 새로운 끝 인덱스)
        """
        import warnings

        warnings.warn(
            "render() is deprecated since v2.3.0 and will be removed in v2.4.0. "
            "Use render_table_structure() + render_table_content() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if table_data.column_count == 0 or table_data.row_count == 0:
            return [], start_index

        requests = []

        # 1. 빈 테이블 생성
        requests.append(
            {
                "insertTable": {
                    "rows": table_data.row_count,
                    "columns": table_data.column_count,
                    "location": {"index": start_index},
                }
            }
        )

        # 2. 모든 행 데이터 수집 (헤더 + 데이터 행)
        all_rows = [table_data.headers] + table_data.rows

        # 3. 셀 내용 삽입 (역순으로 - 인덱스 시프트 방지)
        cell_insertions = []

        for row_idx in range(len(all_rows)):
            for col_idx in range(table_data.column_count):
                cell_index = self._calc_cell_index(
                    start_index, row_idx, col_idx, table_data.column_count
                )
                content = (
                    all_rows[row_idx][col_idx]
                    if col_idx < len(all_rows[row_idx])
                    else ""
                )

                if content:
                    cell_insertions.append(
                        {
                            "row_idx": row_idx,
                            "col_idx": col_idx,
                            "index": cell_index,
                            "content": content,
                            "is_header": row_idx == 0,
                        }
                    )

        # 역순 정렬 (뒤에서부터 삽입)
        cell_insertions.sort(key=lambda x: x["index"], reverse=True)

        # 텍스트 삽입 요청 생성
        for cell in cell_insertions:
            requests.append(
                {
                    "insertText": {
                        "location": {"index": cell["index"]},
                        "text": cell["content"],
                    }
                }
            )

        # 4. 헤더 행 볼드 스타일 적용
        for col_idx in range(table_data.column_count):
            header_content = (
                table_data.headers[col_idx] if col_idx < len(table_data.headers) else ""
            )
            if header_content:
                header_index = self._calc_cell_index(
                    start_index, 0, col_idx, table_data.column_count
                )
                # SKILL.md 표준: 진한 회색 #404040
                requests.append(
                    {
                        "updateTextStyle": {
                            "range": {
                                "startIndex": header_index,
                                "endIndex": header_index + utf16_len(header_content),
                            },
                            "textStyle": {
                                "bold": True,
                                "foregroundColor": {
                                    "color": {
                                        "rgbColor": {
                                            "red": 0.25,
                                            "green": 0.25,
                                            "blue": 0.25,
                                        }
                                    }
                                },
                            },
                            "fields": "bold,foregroundColor",
                        }
                    }
                )

        # 5. 새로운 끝 인덱스 계산
        new_index = self._calc_table_end_index(start_index, table_data)

        return requests, new_index

    def _calc_cell_index(
        self,
        table_start: int,
        row_idx: int,
        col_idx: int,
        col_count: int,
    ) -> int:
        """
        [레거시] 테이블 셀의 삽입 인덱스 계산 (추정값)

        Google Docs 테이블 구조:
        - 테이블 요소: 1
        - 각 행: 1
        - 각 셀: 2 (셀 요소 + 단락)
        """
        base = table_start + 2
        row_offset = row_idx * (1 + col_count * 2)
        col_offset = col_idx * 2 + 1
        return base + row_offset + col_offset

    def _calc_table_end_index(self, table_start: int, table_data: TableData) -> int:
        """
        [레거시] 테이블 끝 인덱스 계산 (추정값)
        """
        size = 1
        row_size = 1 + table_data.column_count * 2
        size += table_data.row_count * row_size

        all_rows = [table_data.headers] + table_data.rows
        for row in all_rows:
            for cell in row:
                size += len(cell)

        return table_start + size + 1
