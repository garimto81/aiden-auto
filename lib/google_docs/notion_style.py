"""
Google Docs 스타일 시스템 (파랑 계열 전문 문서)

Google Docs PRD 변환에 사용되는 전역 표준 스타일을 정의합니다.
SKILL.md (google-workspace) 표준을 따릅니다.

Features:
- 파랑 계열 색상 팔레트 (#1A4D8C, #3373B3, #404040)
- 115% 줄간격, A4 용지, 72pt 여백
- 섹션별 아이콘
- Callout 박스 스타일
"""

from dataclasses import dataclass
from typing import Any

# ============================================================================
# 색상 팔레트 (SKILL.md 표준 - 파랑 계열 전문 문서)
# ============================================================================


def hex_to_rgb(hex_color: str) -> dict[str, float]:
    """HEX 색상을 Google Docs RGB 형식으로 변환"""
    hex_color = hex_color.lstrip("#")
    return {
        "red": int(hex_color[0:2], 16) / 255,
        "green": int(hex_color[2:4], 16) / 255,
        "blue": int(hex_color[4:6], 16) / 255,
    }


NOTION_COLORS = {
    # ============================================
    # 파랑 계열 전문 문서 팔레트 (SKILL.md 표준)
    # ============================================
    # 텍스트 계층 (SKILL.md 표준)
    "text_primary": hex_to_rgb("#404040"),  # 진한 회색 - 본문
    "text_secondary": hex_to_rgb("#666666"),  # 중간 회색 - 메타/캡션
    "text_muted": hex_to_rgb("#999999"),  # 연한 회색 - 힌트 텍스트
    # 제목 색상 (전역 표준 - google-workspace 스킬 정의)
    "heading_primary": hex_to_rgb("#1A4D8C"),  # 진한 파랑 - Title, H1
    "heading_secondary": hex_to_rgb("#3373B3"),  # 밝은 파랑 - H2
    "heading_tertiary": hex_to_rgb("#404040"),  # 진한 회색 - H3
    "heading_accent": hex_to_rgb("#3373B3"),  # 밝은 파랑 - 강조/구분선
    # 배경 색상 (SKILL.md 표준)
    "background": hex_to_rgb("#FFFFFF"),  # 순백
    "background_gray": hex_to_rgb("#F2F2F2"),  # 연한 회색 - 코드/테이블
    "background_warm": hex_to_rgb("#FFF9E6"),  # 연한 노랑 - 경고 배경
    # 강조 색상 (SKILL.md 표준)
    "red": hex_to_rgb("#DC2626"),  # Red
    "orange": hex_to_rgb("#D97706"),  # Orange
    "yellow": hex_to_rgb("#CA8A04"),  # Yellow
    "green": hex_to_rgb("#059669"),  # Green
    "blue": hex_to_rgb("#1A4D8C"),  # 진한 파랑 (Primary)
    "purple": hex_to_rgb("#7C3AED"),  # Purple
    "pink": hex_to_rgb("#DB2777"),  # Pink
    # 하이라이트 배경
    "highlight_red": hex_to_rgb("#FEE2E2"),  # Red 100
    "highlight_orange": hex_to_rgb("#FEF3C7"),  # Orange 100
    "highlight_yellow": hex_to_rgb("#FEF9C3"),  # Yellow 100
    "highlight_green": hex_to_rgb("#D1FAE5"),  # Green 100
    "highlight_blue": hex_to_rgb("#DBEAFE"),  # Blue 100
    "highlight_purple": hex_to_rgb("#EDE9FE"),  # Purple 100
    "highlight_gray": hex_to_rgb("#F2F2F2"),  # Gray
    # 코드 블록 (SKILL.md 표준)
    "code_bg": hex_to_rgb("#F2F2F2"),  # 연한 회색
    "code_text": hex_to_rgb("#404040"),  # 진한 회색
    "code_border": hex_to_rgb("#E6E6E6"),  # 테두리 회색
    # 테두리 및 구분선 (SKILL.md 표준)
    "border": hex_to_rgb("#E6E6E6"),  # 연한 회색 테두리
    "divider": hex_to_rgb("#3373B3"),  # 밝은 파랑 (H1 구분선용)
    # 테이블 (SKILL.md 표준)
    "table_header_bg": hex_to_rgb("#E6E6E6"),  # 연한 회색 헤더 배경
    "table_header_text": hex_to_rgb("#404040"),  # 진한 회색 헤더 텍스트
    "table_border": hex_to_rgb("#CCCCCC"),  # 1pt 회색 테두리
    "table_row_alt": hex_to_rgb("#F9F9F9"),  # 교대 행 배경
}


# ============================================================================
# 폰트 설정
# ============================================================================

NOTION_FONTS = {
    "heading": "Arial",  # 산세리프 (가독성)
    "body": "Arial",  # 산세리프 (가독성)
    "code": "Consolas",  # 고정폭
    "ui": "Segoe UI",  # UI 요소
}

# ============================================================================
# 페이지 설정 (전역 표준 - google-workspace 스킬 기준)
# ============================================================================

PAGE_SETTINGS = {
    # A4 크기 (포인트 단위)
    "page_width": 595.28,  # 210mm = 595.28pt
    "page_height": 841.89,  # 297mm = 841.89pt
    # 여백 (1인치 = 72pt)
    "margin_top": 72,
    "margin_bottom": 72,
    "margin_left": 72,
    "margin_right": 72,
    # 컨텐츠 영역 너비
    "content_width": 451.28,  # 595.28 - 72*2
    # 줄간격
    "line_spacing": 115,  # 115%
}


# ============================================================================
# 타이포그래피 시스템
# ============================================================================

NOTION_TYPOGRAPHY: dict[int | str, dict[str, Any]] = {
    # ============================================
    # 파랑 계열 전문 문서 타이포그래피 (SKILL.md 표준)
    # ============================================
    # Title 스타일 (제목)
    "title": {
        "size": 26,  # 26pt (전역 표준)
        "weight": 700,
        "line_height": 1.15,  # 115% 줄간격
        "space_before": 12,
        "space_after": 0,  # 0pt (줄바꿈 최소화)
        "font": "heading",
        "color": "heading_primary",  # 진한 파랑 #1A4D8C
    },
    # Heading 스타일 (전역 표준)
    1: {
        "size": 18,  # H1: 18pt (전역 표준)
        "weight": 700,
        "line_height": 1.15,  # 115% 줄간격
        "space_before": 18,
        "space_after": 0,  # 0pt (줄바꿈 최소화)
        "font": "heading",
        "color": "heading_primary",  # 진한 파랑 #1A4D8C
        "border_bottom": True,  # 하단 구분선
    },
    2: {
        "size": 14,  # H2: 14pt (전역 표준)
        "weight": 700,
        "line_height": 1.15,
        "space_before": 14,
        "space_after": 0,  # 0pt (줄바꿈 최소화)
        "font": "heading",
        "color": "heading_secondary",  # 밝은 파랑 #3373B3
    },
    3: {
        "size": 12,  # H3: 12pt (전역 표준)
        "weight": 700,
        "line_height": 1.15,
        "space_before": 10,
        "space_after": 0,  # 0pt (줄바꿈 최소화)
        "font": "heading",
        "color": "heading_tertiary",  # 진한 회색 #404040
    },
    4: {
        "size": 11,
        "weight": 600,
        "line_height": 1.15,
        "space_before": 8,
        "space_after": 0,  # 0pt (줄바꿈 최소화)
        "font": "heading",
        "color": "text_primary",
    },
    5: {
        "size": 11,
        "weight": 600,
        "line_height": 1.15,
        "space_before": 6,
        "space_after": 0,  # 0pt (줄바꿈 최소화)
        "font": "heading",
        "color": "text_primary",
    },
    6: {
        "size": 10,
        "weight": 600,
        "line_height": 1.15,
        "space_before": 4,
        "space_after": 0,  # 0pt (줄바꿈 최소화)
        "font": "heading",
        "color": "text_secondary",
    },
    # Body 스타일 (전역 표준)
    "body": {
        "size": 11,  # 11pt
        "weight": 400,
        "line_height": 1.15,  # 115% 줄간격 (전역 표준)
        "space_after": 0,  # 0pt (줄바꿈 최소화)
        "font": "body",
        "color": "text_primary",
    },
    # 코드 스타일 (미니멀)
    "code_inline": {
        "size": 10.5,
        "weight": 400,
        "font": "code",
        "color": "code_text",
        "background": "code_bg",
    },
    "code_block": {
        "size": 10.5,
        "weight": 400,
        "line_height": 1.5,
        "font": "code",
        "color": "text_primary",
        "background": "code_bg",
        "padding": 12,
    },
    # 리스트 스타일
    "list": {
        "size": 11,
        "weight": 400,
        "line_height": 1.55,
        "indent": 20,
        "item_spacing": 0,  # 0pt (줄바꿈 최소화)
        "font": "body",
        "color": "text_primary",
    },
    # 인용문 스타일 (세련된)
    "quote": {
        "size": 11,
        "weight": 400,
        "line_height": 1.6,
        "font": "body",
        "color": "text_secondary",
        "border_color": "blue",  # Royal Blue 왼쪽 테두리
        "border_width": 3,
        "padding": 12,
    },
    # 메타데이터 스타일 (새로 추가)
    "meta": {
        "size": 10,
        "weight": 400,
        "line_height": 1.4,
        "font": "body",
        "color": "text_muted",
    },
}


# ============================================================================
# 섹션 아이콘 매핑
# ============================================================================

SECTION_ICONS: dict[str, str] = {
    # 일반 섹션
    "overview": "📋",
    "introduction": "📝",
    "background": "📚",
    "goals": "🎯",
    "objectives": "🎯",
    # 기술 섹션
    "architecture": "🏗️",
    "technical": "⚙️",
    "implementation": "💻",
    "api": "🔌",
    "data": "💾",
    "database": "🗄️",
    "erd": "📊",
    # 기능 섹션
    "features": "✨",
    "requirements": "📋",
    "specifications": "📐",
    "user": "👤",
    "ux": "🎨",
    "ui": "🖼️",
    # 프로세스 섹션
    "workflow": "🔄",
    "process": "⚡",
    "flow": "➡️",
    "timeline": "📅",
    "schedule": "🗓️",
    "milestones": "🏁",
    # 품질 섹션
    "testing": "🧪",
    "quality": "✅",
    "security": "🔒",
    "performance": "🚀",
    # 배포/운영 섹션
    "deployment": "🚢",
    "infrastructure": "☁️",
    "monitoring": "📈",
    "operations": "🔧",
    # 문서 섹션
    "appendix": "📎",
    "references": "📖",
    "glossary": "📕",
    "changelog": "📝",
}


# ============================================================================
# Callout 스타일
# ============================================================================

CALLOUT_STYLES: dict[str, dict[str, Any]] = {
    "info": {
        "icon": "ℹ️",
        "background": "highlight_blue",
        "border_color": "blue",
    },
    "warning": {
        "icon": "⚠️",
        "background": "highlight_orange",
        "border_color": "orange",
    },
    "success": {
        "icon": "✅",
        "background": "highlight_green",
        "border_color": "green",
    },
    "danger": {
        "icon": "🚨",
        "background": "highlight_red",
        "border_color": "red",
    },
    "tip": {
        "icon": "💡",
        "background": "highlight_yellow",
        "border_color": "yellow",
    },
    "note": {
        "icon": "📝",
        "background": "highlight_gray",
        "border_color": "text_muted",
    },
}


# ============================================================================
# 스타일 유틸리티 클래스
# ============================================================================


@dataclass
class NotionStyle:
    """Notion 스타일 설정 컨테이너 (WSOPTV 전역 표준)"""

    colors: dict[str, dict[str, float]]
    typography: dict[int | str, dict[str, Any]]
    fonts: dict[str, str]
    icons: dict[str, str]
    callouts: dict[str, dict[str, Any]]
    page: dict[str, float]

    @classmethod
    def default(cls) -> "NotionStyle":
        """기본 WSOPTV 전역 표준 스타일 반환"""
        return cls(
            colors=NOTION_COLORS,
            typography=NOTION_TYPOGRAPHY,
            fonts=NOTION_FONTS,
            icons=SECTION_ICONS,
            callouts=CALLOUT_STYLES,
            page=PAGE_SETTINGS,
        )

    def get_color(self, name: str) -> dict[str, float]:
        """색상 이름으로 RGB 값 반환"""
        return self.colors.get(name, self.colors["text_primary"])

    def get_heading_style(self, level: int) -> dict[str, Any]:
        """헤딩 레벨별 스타일 반환"""
        return self.typography.get(level, self.typography[6])

    def get_font(self, style_type: str) -> str:
        """스타일 타입에 맞는 폰트 반환"""
        font_key = self.typography.get(style_type, {}).get("font", "body")
        return self.fonts.get(font_key, self.fonts["body"])

    def get_section_icon(self, section_name: str) -> str | None:
        """섹션 이름에 맞는 아이콘 반환"""
        section_lower = section_name.lower()
        for key, icon in self.icons.items():
            if key in section_lower:
                return icon
        return None

    def get_callout_style(self, callout_type: str) -> dict[str, Any]:
        """Callout 타입별 스타일 반환"""
        return self.callouts.get(callout_type, self.callouts["note"])

    def get_page_style_request(self) -> dict[str, Any]:
        """페이지 스타일 설정 요청 반환 (A4, 72pt 여백)"""
        return {
            "updateDocumentStyle": {
                "documentStyle": {
                    "pageSize": {
                        "width": {"magnitude": self.page["page_width"], "unit": "PT"},
                        "height": {"magnitude": self.page["page_height"], "unit": "PT"},
                    },
                    "marginTop": {"magnitude": self.page["margin_top"], "unit": "PT"},
                    "marginBottom": {
                        "magnitude": self.page["margin_bottom"],
                        "unit": "PT",
                    },
                    "marginLeft": {"magnitude": self.page["margin_left"], "unit": "PT"},
                    "marginRight": {
                        "magnitude": self.page["margin_right"],
                        "unit": "PT",
                    },
                },
                "fields": "pageSize,marginTop,marginBottom,marginLeft,marginRight",
            }
        }

    def get_h1_border_style(self) -> dict[str, Any]:
        """H1 하단 구분선 스타일 반환"""
        return {
            "color": {"color": {"rgbColor": self.colors["heading_accent"]}},
            "width": {"magnitude": 1, "unit": "PT"},
            "padding": {"magnitude": 4, "unit": "PT"},
            "dashStyle": "SOLID",
        }


class NotionStyleMixin:
    """Notion 스타일 적용을 위한 Mixin 클래스"""

    def __init__(self, style: NotionStyle | None = None):
        self.style = style or NotionStyle.default()

    def _build_text_style(
        self,
        size: float | None = None,
        font: str | None = None,
        bold: bool = False,
        italic: bool = False,
        color: str | None = None,
        background: str | None = None,
        link: str | None = None,
    ) -> dict[str, Any]:
        """Google Docs textStyle 객체 생성"""
        text_style: dict[str, Any] = {}
        fields: list[str] = []

        if size:
            text_style["fontSize"] = {"magnitude": size, "unit": "PT"}
            fields.append("fontSize")

        if font:
            font_name = self.style.fonts.get(font, font)
            text_style["weightedFontFamily"] = {
                "fontFamily": font_name,
                "weight": 700 if bold else 400,
            }
            fields.append("weightedFontFamily")
        elif bold:
            text_style["bold"] = True
            fields.append("bold")

        if italic:
            text_style["italic"] = True
            fields.append("italic")

        if color:
            text_style["foregroundColor"] = {
                "color": {"rgbColor": self.style.get_color(color)}
            }
            fields.append("foregroundColor")

        if background:
            text_style["backgroundColor"] = {
                "color": {"rgbColor": self.style.get_color(background)}
            }
            fields.append("backgroundColor")

        if link:
            text_style["link"] = {"url": link}
            fields.append("link")

        return {"textStyle": text_style, "fields": ",".join(fields)}

    def _build_paragraph_style(
        self,
        named_style: str | None = None,
        space_before: float | None = None,
        space_after: float | None = None,
        line_height: float | None = None,
        indent_start: float | None = None,
        indent_end: float | None = None,
        background: str | None = None,
        border_left: dict | None = None,
    ) -> dict[str, Any]:
        """Google Docs paragraphStyle 객체 생성"""
        para_style: dict[str, Any] = {}
        fields: list[str] = []

        if named_style:
            para_style["namedStyleType"] = named_style
            fields.append("namedStyleType")

        if space_before is not None:
            para_style["spaceAbove"] = {"magnitude": space_before, "unit": "PT"}
            fields.append("spaceAbove")

        if space_after is not None:
            para_style["spaceBelow"] = {"magnitude": space_after, "unit": "PT"}
            fields.append("spaceBelow")

        if line_height is not None:
            para_style["lineSpacing"] = line_height * 100
            fields.append("lineSpacing")

        if indent_start is not None:
            para_style["indentStart"] = {"magnitude": indent_start, "unit": "PT"}
            fields.append("indentStart")

        if indent_end is not None:
            para_style["indentEnd"] = {"magnitude": indent_end, "unit": "PT"}
            fields.append("indentEnd")

        if background:
            para_style["shading"] = {
                "backgroundColor": {
                    "color": {"rgbColor": self.style.get_color(background)}
                }
            }
            fields.append("shading")

        if border_left:
            para_style["borderLeft"] = border_left
            fields.append("borderLeft")

        return {"paragraphStyle": para_style, "fields": ",".join(fields)}


# ============================================================================
# 편의 함수
# ============================================================================


def get_default_style() -> NotionStyle:
    """기본 Notion 스타일 인스턴스 반환"""
    return NotionStyle.default()
