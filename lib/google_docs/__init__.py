"""
Google Docs PRD Converter - 공통 모듈

PRD 마크다운 파일을 Google Docs 네이티브 형식으로 변환합니다.

Usage:
    from lib.google_docs import MarkdownToDocsConverter, create_google_doc

    # 변환
    converter = MarkdownToDocsConverter(markdown_content)
    requests = converter.parse()

    # 문서 생성
    doc_url = create_google_doc(title, markdown_content)
"""

from .models import TextSegment, TableData, TableCell, ConversionResult
from .auth import get_credentials, get_sheets_credentials
from .converter import MarkdownToDocsConverter, create_google_doc
from .table_renderer import NativeTableRenderer
from .notion_style import (
    NOTION_COLORS,
    NOTION_FONTS,
    NOTION_TYPOGRAPHY,
    SECTION_ICONS,
    CALLOUT_STYLES,
    NotionStyle,
    NotionStyleMixin,
    get_default_style,
    hex_to_rgb,
)
from .diagram_generator import DiagramGenerator, create_generator
from .image_inserter import ImageInserter, create_inserter
from .batch_processor import BatchConverter, ConvertResult as BatchConvertResult
from .auto_trigger import AutoTriggerHandler
from .project_registry import ProjectRegistry, get_project_folder_id, get_default_folder_id
from .drive_guardian import DriveGuardian, AuditReport, FixPlan
from .sheets import SheetsClient, parse_sheet_url

__version__ = "1.4.0"
__all__ = [
    # Models
    "TextSegment",
    "TableData",
    "TableCell",
    "ConversionResult",
    # Auth
    "get_credentials",
    "get_sheets_credentials",
    # Converter
    "MarkdownToDocsConverter",
    "create_google_doc",
    "NativeTableRenderer",
    # Notion Style
    "NOTION_COLORS",
    "NOTION_FONTS",
    "NOTION_TYPOGRAPHY",
    "SECTION_ICONS",
    "CALLOUT_STYLES",
    "NotionStyle",
    "NotionStyleMixin",
    "get_default_style",
    "hex_to_rgb",
    # Diagram Generator
    "DiagramGenerator",
    "create_generator",
    # Image Inserter
    "ImageInserter",
    "create_inserter",
    # Batch Processor (Phase 1)
    "BatchConverter",
    "BatchConvertResult",
    # Auto Trigger (Phase 1)
    "AutoTriggerHandler",
    # Project Registry (Drive 프로젝트 매핑)
    "ProjectRegistry",
    "get_project_folder_id",
    "get_default_folder_id",
    # Drive Guardian (구조 감사)
    "DriveGuardian",
    "AuditReport",
    "FixPlan",
    # Sheets
    "SheetsClient",
    "parse_sheet_url",
]
