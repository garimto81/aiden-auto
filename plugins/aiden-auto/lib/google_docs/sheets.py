"""
Google Sheets 읽기/쓰기 모듈

Google Sheets API를 사용하여 스프레드시트 데이터를 읽고 씁니다.

Usage:
    from lib.google_docs.sheets import SheetsClient

    client = SheetsClient()
    data = client.read_sheet("spreadsheet_id", "Sheet1!A1:Z100")
"""

import json
import re
from typing import Optional

from googleapiclient.discovery import build

from .auth import get_sheets_credentials


def parse_sheet_url(url: str) -> dict:
    """
    Google Sheets URL에서 spreadsheet_id와 gid를 추출합니다.

    Args:
        url: Google Sheets URL

    Returns:
        dict: {"spreadsheet_id": str, "gid": str | None}
    """
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise ValueError(f"유효한 Google Sheets URL이 아닙니다: {url}")

    spreadsheet_id = match.group(1)

    gid_match = re.search(r"[?&]gid=(\d+)", url)
    gid = gid_match.group(1) if gid_match else None

    return {"spreadsheet_id": spreadsheet_id, "gid": gid}


class SheetsClient:
    """Google Sheets API 클라이언트"""

    def __init__(self):
        creds = get_sheets_credentials()
        self._service = build("sheets", "v4", credentials=creds)
        self._sheets = self._service.spreadsheets()

    def get_metadata(self, spreadsheet_id: str) -> dict:
        """스프레드시트 메타데이터 조회 (제목, 시트 목록 등)"""
        result = self._sheets.get(
            spreadsheetId=spreadsheet_id,
            fields="spreadsheetId,properties.title,sheets.properties",
        ).execute()
        return result

    def get_sheet_name_by_gid(self, spreadsheet_id: str, gid: str) -> Optional[str]:
        """gid로 시트 이름을 찾습니다."""
        meta = self.get_metadata(spreadsheet_id)
        gid_int = int(gid)
        for sheet in meta.get("sheets", []):
            props = sheet.get("properties", {})
            if props.get("sheetId") == gid_int:
                return props.get("title")
        return None

    def read_sheet(
        self,
        spreadsheet_id: str,
        range_notation: str = "",
        value_render: str = "FORMATTED_VALUE",
    ) -> list[list[str]]:
        """
        시트 데이터를 읽습니다.

        Args:
            spreadsheet_id: 스프레드시트 ID
            range_notation: A1 표기법 범위 (예: "Sheet1!A1:Z100", 빈 문자열이면 전체)
            value_render: 값 렌더링 옵션 (FORMATTED_VALUE, UNFORMATTED_VALUE, FORMULA)

        Returns:
            list[list[str]]: 2D 배열 형태의 시트 데이터
        """
        result = self._sheets.values().get(
            spreadsheetId=spreadsheet_id,
            range=range_notation,
            valueRenderOption=value_render,
        ).execute()
        return result.get("values", [])

    def read_from_url(
        self,
        url: str,
        range_notation: Optional[str] = None,
        value_render: str = "FORMATTED_VALUE",
    ) -> dict:
        """
        URL에서 직접 시트 데이터를 읽습니다.

        Args:
            url: Google Sheets URL
            range_notation: A1 표기법 범위 (None이면 gid에 해당하는 시트 전체)
            value_render: 값 렌더링 옵션

        Returns:
            dict: {"title": str, "sheet_name": str, "data": list[list[str]], "rows": int, "cols": int}
        """
        parsed = parse_sheet_url(url)
        spreadsheet_id = parsed["spreadsheet_id"]
        gid = parsed["gid"]

        meta = self.get_metadata(spreadsheet_id)
        title = meta.get("properties", {}).get("title", "Unknown")

        if range_notation:
            sheet_range = range_notation
            sheet_name = range_notation.split("!")[0] if "!" in range_notation else "Unknown"
        elif gid:
            sheet_name = self.get_sheet_name_by_gid(spreadsheet_id, gid)
            if not sheet_name:
                raise ValueError(f"gid={gid}에 해당하는 시트를 찾을 수 없습니다.")
            sheet_range = f"'{sheet_name}'"
        else:
            first_sheet = meta.get("sheets", [{}])[0]
            sheet_name = first_sheet.get("properties", {}).get("title", "Sheet1")
            sheet_range = f"'{sheet_name}'"

        data = self.read_sheet(spreadsheet_id, sheet_range, value_render)

        rows = len(data)
        cols = max(len(row) for row in data) if data else 0

        return {
            "title": title,
            "sheet_name": sheet_name,
            "data": data,
            "rows": rows,
            "cols": cols,
        }

    def list_sheets(self, spreadsheet_id: str) -> list[dict]:
        """스프레드시트의 모든 시트 목록을 반환합니다."""
        meta = self.get_metadata(spreadsheet_id)
        sheets = []
        for sheet in meta.get("sheets", []):
            props = sheet.get("properties", {})
            sheets.append({
                "title": props.get("title"),
                "sheetId": props.get("sheetId"),
                "index": props.get("index"),
                "rowCount": props.get("gridProperties", {}).get("rowCount"),
                "columnCount": props.get("gridProperties", {}).get("columnCount"),
            })
        return sheets

    def to_markdown_table(self, data: list[list[str]], max_rows: int = 50) -> str:
        """2D 데이터를 Markdown 테이블로 변환합니다."""
        if not data:
            return "(빈 시트)"

        # 헤더
        header = data[0]
        col_count = len(header)

        lines = []
        lines.append("| " + " | ".join(str(c) for c in header) + " |")
        lines.append("| " + " | ".join("---" for _ in range(col_count)) + " |")

        # 데이터 행
        for row in data[1:max_rows + 1]:
            padded = row + [""] * (col_count - len(row))
            lines.append("| " + " | ".join(str(c) for c in padded[:col_count]) + " |")

        if len(data) - 1 > max_rows:
            lines.append(f"\n... ({len(data) - 1 - max_rows}행 생략)")

        return "\n".join(lines)

    def to_json(self, data: list[list[str]], max_rows: int = 100) -> str:
        """2D 데이터를 JSON으로 변환합니다 (첫 행을 키로 사용)."""
        if not data or len(data) < 2:
            return "[]"

        headers = data[0]
        rows = []
        for row in data[1:max_rows + 1]:
            obj = {}
            for i, header in enumerate(headers):
                obj[header] = row[i] if i < len(row) else ""
            rows.append(obj)

        return json.dumps(rows, indent=2, ensure_ascii=False)
