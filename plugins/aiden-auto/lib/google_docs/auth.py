"""
OAuth 2.0 인증 모듈

Google Docs/Drive API 인증을 처리합니다.
"""

import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


def _get_project_root() -> Path:
    """프로젝트 루트 경로 반환 (환경변수 > 자동 탐지)"""
    # 1. 환경변수 확인
    env_root = os.environ.get("CLAUDE_PROJECT_ROOT")
    if env_root:
        return Path(env_root)

    # 2. 현재 파일 기준으로 프로젝트 루트 탐지
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "CLAUDE.md").exists() or (parent / ".git").exists():
            return parent

    # 3. 기본값 (fallback)
    return Path("C:/claude")


# 프로젝트 루트 기반 경로 설정
PROJECT_ROOT = _get_project_root()
CREDENTIALS_FILE = PROJECT_ROOT / "json" / "desktop_credentials.json"
TOKEN_FILE = PROJECT_ROOT / "json" / "token.json"

# Google Docs + Drive 권한
SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

# Sheets 전용 토큰 및 권한
TOKEN_SHEETS_FILE = PROJECT_ROOT / "json" / "token_sheets.json"
SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# 공유 폴더 ID (Google AI Studio 폴더)
DEFAULT_FOLDER_ID = "1JwdlUe_v4Ug-yQ0veXTldFl6C24GH8hW"


def get_credentials() -> Credentials:
    """
    OAuth 2.0 인증 정보 획득

    Returns:
        Credentials: Google API 인증 정보
    """
    creds = None

    # 기존 토큰 확인
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    # 토큰이 없거나 만료된 경우
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # 토큰 갱신
            creds.refresh(Request())
        else:
            # 새로운 인증 플로우
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"OAuth credentials file not found: {CREDENTIALS_FILE}\nDownload from Google Cloud Console."
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # 토큰 저장
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


def get_sheets_credentials() -> Credentials:
    """
    Google Sheets API용 OAuth 2.0 인증 정보 획득

    token_sheets.json을 사용하며, spreadsheets + drive scope를 가집니다.

    Returns:
        Credentials: Google Sheets API 인증 정보
    """
    creds = None

    if TOKEN_SHEETS_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_SHEETS_FILE), SHEETS_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"OAuth credentials file not found: {CREDENTIALS_FILE}\nDownload from Google Cloud Console."
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SHEETS_SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_SHEETS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_SHEETS_FILE, "w") as token:
            token.write(creds.to_json())

    return creds
