"""
Google Docs 문서 빌더

테이블 포함 문서를 안정적으로 생성하기 위한 순차 실행 빌더.
converter의 인덱스 문제를 해결합니다.
"""

import json
import re
from pathlib import Path
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from .notion_style import NotionStyle, PAGE_SETTINGS


class GoogleDocsBuilder:
    """Google Docs 문서 빌더 - 테이블 포함 문서 안정적 생성"""

    DEFAULT_TOKEN_PATH = _get_project_root() / "json" / "token.json"

    # 전역 표준 색상
    COLORS = {
        "primary_blue": {"red": 0.10, "green": 0.30, "blue": 0.55},  # #1A4D8C
        "accent_blue": {"red": 0.20, "green": 0.45, "blue": 0.70},  # #3373B3
        "dark_gray": {"red": 0.25, "green": 0.25, "blue": 0.25},  # #404040
        "table_header_bg": {"red": 0.90, "green": 0.90, "blue": 0.90},
    }

    def _strip_markdown(self, text: str) -> tuple[str, list[dict]]:
        """
        마크다운 기호 제거 및 스타일 정보 추출

        Returns:
            tuple: (plain_text, styles) - 스타일은 [{start, end, bold, italic}] 형태
        """
        styles = []

        # 정규식 패턴들
        patterns = [
            (r"\*\*(.+?)\*\*", "bold"),
            (r"__(.+?)__", "bold"),
            (r"\*(.+?)\*", "italic"),
            (r"_(.+?)_", "italic"),
        ]

        # 모든 매치 찾기
        all_matches = []
        for pattern, style in patterns:
            for match in re.finditer(pattern, text):
                all_matches.append((match.start(), match.end(), match.group(1), style))

        # 위치순 정렬 및 겹침 제거
        all_matches.sort(key=lambda x: x[0])
        filtered_matches = []
        last_end = 0
        for match in all_matches:
            if match[0] >= last_end:
                filtered_matches.append(match)
                last_end = match[1]

        # plain text 생성
        plain_parts = []
        current_pos = 0
        plain_offset = 0

        for start, end, content, style in filtered_matches:
            if start > current_pos:
                plain_parts.append(text[current_pos:start])
                plain_offset += start - current_pos

            styles.append(
                {
                    "start": plain_offset,
                    "end": plain_offset + len(content),
                    "bold": style == "bold",
                    "italic": style == "italic",
                }
            )

            plain_parts.append(content)
            plain_offset += len(content)
            current_pos = end

        if current_pos < len(text):
            plain_parts.append(text[current_pos:])

        return "".join(plain_parts), styles

    def __init__(self, token_path: Optional[Path] = None):
        self.token_path = token_path or self.DEFAULT_TOKEN_PATH
        self._credentials = None
        self._docs_service = None
        self._drive_service = None
        self.doc_id = None
        self.style = NotionStyle.default()

    def _get_credentials(self) -> Credentials:
        """인증 정보 로드"""
        if self._credentials and self._credentials.valid:
            return self._credentials

        with open(self.token_path, "r", encoding="utf-8") as f:
            token_data = json.load(f)

        self._credentials = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
        )

        if self._credentials.expired and self._credentials.refresh_token:
            self._credentials.refresh(Request())
            token_data["token"] = self._credentials.token
            with open(self.token_path, "w", encoding="utf-8") as f:
                json.dump(token_data, f, indent=2)

        return self._credentials

    @property
    def docs_service(self):
        """Google Docs API 서비스"""
        if self._docs_service is None:
            creds = self._get_credentials()
            self._docs_service = build("docs", "v1", credentials=creds)
        return self._docs_service

    @property
    def drive_service(self):
        """Google Drive API 서비스"""
        if self._drive_service is None:
            creds = self._get_credentials()
            self._drive_service = build("drive", "v3", credentials=creds)
        return self._drive_service

    def create_document(self, title: str, folder_id: Optional[str] = None) -> str:
        """새 문서 생성"""
        doc = self.docs_service.documents().create(body={"title": title}).execute()
        self.doc_id = doc["documentId"]

        # 폴더로 이동 (옵션)
        if folder_id:
            try:
                file_info = (
                    self.drive_service.files()
                    .get(fileId=self.doc_id, fields="parents")
                    .execute()
                )
                current_parents = ",".join(file_info.get("parents", []))
                self.drive_service.files().update(
                    fileId=self.doc_id,
                    addParents=folder_id,
                    removeParents=current_parents,
                ).execute()
            except Exception:
                pass  # Drive API 권한 없으면 무시

        return self.doc_id

    def apply_page_style(self):
        """페이지 스타일 적용 (A4, 72pt 여백, 115% 줄간격)"""
        requests = [self.style.get_page_style_request()]
        self.docs_service.documents().batchUpdate(
            documentId=self.doc_id, body={"requests": requests}
        ).execute()

    def get_current_end_index(self) -> int:
        """현재 문서 끝 인덱스 조회"""
        doc = self.docs_service.documents().get(documentId=self.doc_id).execute()
        return max(el.get("endIndex", 1) for el in doc["body"]["content"])

    def insert_text(self, text: str, index: Optional[int] = None) -> int:
        """텍스트 삽입 및 새 인덱스 반환"""
        if index is None:
            index = self.get_current_end_index() - 1

        self.docs_service.documents().batchUpdate(
            documentId=self.doc_id,
            body={
                "requests": [
                    {"insertText": {"location": {"index": index}, "text": text}}
                ]
            },
        ).execute()

        return index + len(text)

    def insert_title(self, text: str):
        """제목 삽입 (전역 표준 스타일)"""
        idx = self.get_current_end_index() - 1
        full_text = text + "\n\n"

        self.insert_text(full_text, idx)

        # 스타일 적용
        self.docs_service.documents().batchUpdate(
            documentId=self.doc_id,
            body={
                "requests": [
                    {
                        "updateTextStyle": {
                            "range": {"startIndex": idx, "endIndex": idx + len(text)},
                            "textStyle": {
                                "foregroundColor": {
                                    "color": {"rgbColor": self.COLORS["primary_blue"]}
                                },
                                "bold": True,
                                "fontSize": {"magnitude": 26, "unit": "PT"},
                            },
                            "fields": "foregroundColor,bold,fontSize",
                        }
                    },
                    {
                        "updateParagraphStyle": {
                            "range": {
                                "startIndex": idx,
                                "endIndex": idx + len(text) + 1,
                            },
                            "paragraphStyle": {"namedStyleType": "TITLE"},
                            "fields": "namedStyleType",
                        }
                    },
                ]
            },
        ).execute()

    def insert_heading(self, text: str, level: int = 1):
        """헤딩 삽입 (전역 표준 스타일)"""
        idx = self.get_current_end_index() - 1
        full_text = text + "\n"

        self.insert_text(full_text, idx)

        # 레벨별 스타일
        styles = {
            1: {"color": self.COLORS["primary_blue"], "size": 18, "border": True},
            2: {"color": self.COLORS["accent_blue"], "size": 14, "border": False},
            3: {"color": self.COLORS["dark_gray"], "size": 12, "border": False},
        }
        style = styles.get(level, styles[3])

        requests = [
            {
                "updateTextStyle": {
                    "range": {"startIndex": idx, "endIndex": idx + len(text)},
                    "textStyle": {
                        "foregroundColor": {"color": {"rgbColor": style["color"]}},
                        "bold": True,
                        "fontSize": {"magnitude": style["size"], "unit": "PT"},
                    },
                    "fields": "foregroundColor,bold,fontSize",
                }
            },
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": idx, "endIndex": idx + len(text) + 1},
                    "paragraphStyle": {"namedStyleType": f"HEADING_{level}"},
                    "fields": "namedStyleType",
                }
            },
        ]

        # H1에 하단 구분선
        if style["border"]:
            requests.append(
                {
                    "updateParagraphStyle": {
                        "range": {"startIndex": idx, "endIndex": idx + len(text) + 1},
                        "paragraphStyle": {
                            "borderBottom": self.style.get_h1_border_style()
                        },
                        "fields": "borderBottom",
                    }
                }
            )

        self.docs_service.documents().batchUpdate(
            documentId=self.doc_id, body={"requests": requests}
        ).execute()

    def insert_table(self, rows: list[list[str]]) -> int:
        """테이블 삽입 (마크다운 인라인 스타일 지원)"""
        if not rows:
            return self.get_current_end_index()

        idx = self.get_current_end_index() - 1
        num_rows = len(rows)
        num_cols = len(rows[0]) if rows else 0

        # 1. 테이블 생성
        self.docs_service.documents().batchUpdate(
            documentId=self.doc_id,
            body={
                "requests": [
                    {
                        "insertTable": {
                            "location": {"index": idx},
                            "rows": num_rows,
                            "columns": num_cols,
                        }
                    }
                ]
            },
        ).execute()

        # 2. 문서 다시 로드하여 테이블 구조 확인
        doc = self.docs_service.documents().get(documentId=self.doc_id).execute()

        # 테이블 찾기
        table_element = None
        for element in doc["body"]["content"]:
            if "table" in element and element["startIndex"] >= idx:
                table_element = element
                break

        if not table_element:
            return self.get_current_end_index()

        # 3. 셀에 텍스트 삽입 (역순) - 마크다운 파싱 적용
        table = table_element["table"]
        requests = []
        cell_style_info = []  # 스타일 정보 저장

        for row_idx in range(num_rows - 1, -1, -1):
            row = table["tableRows"][row_idx]
            for col_idx in range(num_cols - 1, -1, -1):
                cell = row["tableCells"][col_idx]
                cell_content = cell["content"]
                if cell_content:
                    cell_start = cell_content[0]["startIndex"]
                    original_text = (
                        rows[row_idx][col_idx] if col_idx < len(rows[row_idx]) else ""
                    )
                    if original_text:
                        # 마크다운 파싱 (** 제거)
                        plain_text, styles = self._strip_markdown(original_text)

                        requests.append(
                            {
                                "insertText": {
                                    "location": {"index": cell_start},
                                    "text": plain_text,  # 마크다운 기호 제거된 텍스트
                                }
                            }
                        )

                        # 스타일 정보 저장
                        if styles:
                            cell_style_info.append(
                                {
                                    "cell_start": cell_start,
                                    "styles": styles,
                                    "row_idx": row_idx,
                                }
                            )

        if requests:
            self.docs_service.documents().batchUpdate(
                documentId=self.doc_id, body={"requests": requests}
            ).execute()

        # 4. 문서 재조회 후 스타일 적용
        doc = self.docs_service.documents().get(documentId=self.doc_id).execute()

        # 테이블 다시 찾기
        for element in doc["body"]["content"]:
            if "table" in element and element["startIndex"] >= idx:
                table_element = element
                break

        if table_element and "table" in table_element:
            table = table_element["table"]
            style_requests = []

            # 4-1. 헤더 행 전체 볼드 + 색상
            header_row = table["tableRows"][0]
            for col_idx, cell in enumerate(header_row["tableCells"]):
                cell_content = cell["content"]
                if cell_content:
                    para = cell_content[0]
                    if "paragraph" in para:
                        elements = para["paragraph"].get("elements", [])
                        for el in elements:
                            if "textRun" in el:
                                text = el["textRun"].get("content", "").strip()
                                if text:
                                    start = el["startIndex"]
                                    end = el["endIndex"] - 1
                                    style_requests.append(
                                        {
                                            "updateTextStyle": {
                                                "range": {
                                                    "startIndex": start,
                                                    "endIndex": end,
                                                },
                                                "textStyle": {
                                                    "bold": True,
                                                    "foregroundColor": {
                                                        "color": {
                                                            "rgbColor": self.COLORS[
                                                                "dark_gray"
                                                            ]
                                                        }
                                                    },
                                                },
                                                "fields": "bold,foregroundColor",
                                            }
                                        }
                                    )

            # 4-2. 데이터 행 색상 + 인라인 스타일
            for row_idx in range(1, num_rows):
                row = table["tableRows"][row_idx]
                for col_idx, cell in enumerate(row["tableCells"]):
                    cell_content = cell["content"]
                    if cell_content:
                        para = cell_content[0]
                        if "paragraph" in para:
                            elements = para["paragraph"].get("elements", [])
                            for el in elements:
                                if "textRun" in el:
                                    text = el["textRun"].get("content", "").strip()
                                    if text:
                                        start = el["startIndex"]
                                        end = el["endIndex"] - 1
                                        # 본문 색상 적용
                                        style_requests.append(
                                            {
                                                "updateTextStyle": {
                                                    "range": {
                                                        "startIndex": start,
                                                        "endIndex": end,
                                                    },
                                                    "textStyle": {
                                                        "foregroundColor": {
                                                            "color": {
                                                                "rgbColor": self.COLORS[
                                                                    "dark_gray"
                                                                ]
                                                            }
                                                        }
                                                    },
                                                    "fields": "foregroundColor",
                                                }
                                            }
                                        )

            # 4-3. 인라인 스타일 적용 (볼드, 이탤릭)
            for info in cell_style_info:
                if info["row_idx"] == 0:  # 헤더는 이미 볼드
                    continue

                row = table["tableRows"][info["row_idx"]]
                for cell in row["tableCells"]:
                    cell_content = cell["content"]
                    if cell_content:
                        para = cell_content[0]
                        if "paragraph" in para:
                            para_start = para.get("startIndex", 0)
                            for style in info["styles"]:
                                style_fields = []
                                text_style = {}

                                if style.get("bold"):
                                    text_style["bold"] = True
                                    style_fields.append("bold")

                                if style.get("italic"):
                                    text_style["italic"] = True
                                    style_fields.append("italic")

                                if style_fields:
                                    style_requests.append(
                                        {
                                            "updateTextStyle": {
                                                "range": {
                                                    "startIndex": para_start
                                                    + style["start"],
                                                    "endIndex": para_start
                                                    + style["end"],
                                                },
                                                "textStyle": text_style,
                                                "fields": ",".join(style_fields),
                                            }
                                        }
                                    )

            if style_requests:
                self.docs_service.documents().batchUpdate(
                    documentId=self.doc_id, body={"requests": style_requests}
                ).execute()

        return self.get_current_end_index()

    def insert_paragraph(self, text: str):
        """일반 문단 삽입"""
        self.insert_text(text + "\n")

    def apply_line_spacing(self):
        """전체 줄간격 적용 (115%)"""
        end_index = self.get_current_end_index()
        self.docs_service.documents().batchUpdate(
            documentId=self.doc_id,
            body={
                "requests": [
                    {
                        "updateParagraphStyle": {
                            "range": {"startIndex": 1, "endIndex": end_index - 1},
                            "paragraphStyle": {
                                "lineSpacing": PAGE_SETTINGS["line_spacing"]
                            },
                            "fields": "lineSpacing",
                        }
                    }
                ]
            },
        ).execute()

    def get_document_url(self) -> str:
        """문서 URL 반환"""
        return f"https://docs.google.com/document/d/{self.doc_id}/edit"
