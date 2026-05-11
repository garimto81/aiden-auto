"""
Google Docs 이미지 삽입 유틸리티

Drive 업로드 → 공개 URL 생성 → Docs 삽입

Features:
- Google Drive 이미지 업로드
- 공개 URL 생성
- Google Docs 특정 위치에 이미지 삽입
- 텍스트 검색 후 이미지 삽입

Usage:
    from lib.google_docs.image_inserter import ImageInserter
    from lib.google_docs.auth import get_credentials

    creds = get_credentials()
    inserter = ImageInserter(creds)

    # Drive에 업로드
    file_id, image_url = inserter.upload_to_drive(Path('diagram.png'))

    # Docs에 삽입
    inserter.insert_image_at_position(doc_id, image_url, position=100, width=400)
"""

import re
from pathlib import Path
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class ImageInserter:
    """이미지를 Google Docs에 삽입"""

    def __init__(self, credentials, docs_service=None, drive_service=None):
        """
        Args:
            credentials: Google OAuth 인증 정보
            docs_service: Google Docs API 서비스 (없으면 자동 생성)
            drive_service: Google Drive API 서비스 (없으면 자동 생성)
        """
        self.credentials = credentials
        self.docs_service = docs_service or build("docs", "v1", credentials=credentials)
        self.drive_service = drive_service or build(
            "drive", "v3", credentials=credentials
        )

    def find_existing_file(
        self,
        file_name: str,
        folder_id: Optional[str] = None,
    ) -> Optional[tuple[str, str]]:
        """
        Drive에서 동일 이름의 기존 파일 검색

        Args:
            file_name: 파일명
            folder_id: 폴더 ID (없으면 전체 검색)

        Returns:
            (file_id, image_url) 또는 None
        """
        query_parts = [f"name='{file_name}'", "trashed=false"]
        if folder_id:
            query_parts.append(f"'{folder_id}' in parents")

        query = " and ".join(query_parts)

        try:
            results = self.drive_service.files().list(
                q=query,
                pageSize=1,
                fields="files(id, thumbnailLink)"
            ).execute()

            files = results.get("files", [])
            if files:
                file_id = files[0]["id"]
                thumbnail_link = files[0].get("thumbnailLink", "")

                if thumbnail_link and "lh3.googleusercontent.com" in thumbnail_link:
                    image_url = re.sub(r"=s\d+$", "=s0", thumbnail_link)
                else:
                    image_url = f"https://lh3.googleusercontent.com/d/{file_id}"

                return file_id, image_url

        except Exception:
            pass

        return None

    def upload_to_drive(
        self,
        file_path: Path,
        folder_id: Optional[str] = None,
        make_public: bool = True,
        file_name: Optional[str] = None,
        skip_duplicates: bool = True,
    ) -> tuple[str, str]:
        """
        Google Drive에 이미지 업로드

        Args:
            file_path: 업로드할 파일 경로
            folder_id: 대상 폴더 ID (없으면 루트)
            make_public: 공개 URL 생성 여부
            file_name: 저장할 파일명 (없으면 원본 파일명)
            skip_duplicates: True이면 동일 이름 파일이 있으면 재사용

        Returns:
            (file_id, public_url) 튜플
        """
        file_path = Path(file_path)
        target_name = file_name or file_path.name

        # 중복 검사 (skip_duplicates=True인 경우)
        if skip_duplicates:
            existing = self.find_existing_file(target_name, folder_id)
            if existing:
                # 기존 파일 재사용
                return existing

        # 파일 메타데이터
        file_metadata = {
            "name": target_name,
        }

        if folder_id:
            file_metadata["parents"] = [folder_id]

        # MIME 타입 결정
        suffix = file_path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".svg": "image/svg+xml",
        }
        mimetype = mime_types.get(suffix, "image/png")

        # 업로드
        media = MediaFileUpload(str(file_path), mimetype=mimetype, resumable=True)

        file = (
            self.drive_service.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id, webContentLink, webViewLink",
            )
            .execute()
        )

        file_id = file.get("id")

        # 공개 권한 설정
        if make_public:
            try:
                self.drive_service.permissions().create(
                    fileId=file_id, body={"type": "anyone", "role": "reader"}
                ).execute()
            except Exception as e:
                print(f"공개 권한 설정 실패: {e}")

        # 직접 접근 URL 생성 (lh3.googleusercontent.com 형식 사용)
        # 기존 drive.google.com/uc?id= 는 deprecated됨
        # thumbnailLink에서 lh3 URL 추출
        try:
            file_meta = self.drive_service.files().get(
                fileId=file_id,
                fields="thumbnailLink"
            ).execute()
            thumbnail_link = file_meta.get("thumbnailLink", "")

            if thumbnail_link and "lh3.googleusercontent.com" in thumbnail_link:
                # =s220 등의 크기 제한을 =s0 (원본 크기)로 변경
                image_url = re.sub(r"=s\d+$", "=s0", thumbnail_link)
            else:
                # 폴백: 직접 콘텐츠 링크 사용
                image_url = f"https://lh3.googleusercontent.com/d/{file_id}"
        except Exception:
            # 최종 폴백
            image_url = f"https://lh3.googleusercontent.com/d/{file_id}"

        return file_id, image_url

    def insert_image_at_position(
        self,
        doc_id: str,
        image_url: str,
        position: int,
        width: int = 400,
    ) -> bool:
        """
        문서의 특정 위치에 이미지 삽입

        Args:
            doc_id: 문서 ID
            image_url: 이미지 URL (Drive 공개 URL)
            position: 삽입 위치 (인덱스)
            width: 이미지 너비 (PT)

        Returns:
            성공 여부
        """
        requests = [
            {
                "insertInlineImage": {
                    "location": {"index": position},
                    "uri": image_url,
                    "objectSize": {"width": {"magnitude": width, "unit": "PT"}},
                }
            }
        ]

        try:
            self.docs_service.documents().batchUpdate(
                documentId=doc_id, body={"requests": requests}
            ).execute()
            return True
        except Exception as e:
            print(f"이미지 삽입 실패: {e}")
            return False

    def find_text_position(
        self,
        doc_id: str,
        search_text: str,
    ) -> Optional[int]:
        """
        문서에서 텍스트 위치 찾기

        Args:
            doc_id: 문서 ID
            search_text: 검색할 텍스트

        Returns:
            텍스트 끝 위치 (없으면 None)
        """
        doc = self.docs_service.documents().get(documentId=doc_id).execute()
        body_content = doc.get("body", {}).get("content", [])

        for element in body_content:
            if "paragraph" in element:
                para = element["paragraph"]
                for para_element in para.get("elements", []):
                    text_run = para_element.get("textRun", {})
                    content = text_run.get("content", "")

                    if search_text in content:
                        # 텍스트 끝 위치 반환
                        return para_element.get("endIndex", 0)

        return None

    def insert_image_after_text(
        self,
        doc_id: str,
        image_url: str,
        search_text: str,
        width: int = 400,
        add_newline: bool = True,
    ) -> bool:
        """
        특정 텍스트 다음에 이미지 삽입

        Args:
            doc_id: 문서 ID
            image_url: 이미지 URL
            search_text: 검색할 텍스트
            width: 이미지 너비 (PT)
            add_newline: 줄바꿈 추가 여부

        Returns:
            성공 여부
        """
        position = self.find_text_position(doc_id, search_text)

        if position is None:
            print(f"텍스트를 찾을 수 없습니다: {search_text}")
            return False

        # 줄바꿈 후 이미지 삽입
        requests = []

        if add_newline:
            requests.append(
                {"insertText": {"location": {"index": position}, "text": "\n"}}
            )
            position += 1

        requests.append(
            {
                "insertInlineImage": {
                    "location": {"index": position},
                    "uri": image_url,
                    "objectSize": {"width": {"magnitude": width, "unit": "PT"}},
                }
            }
        )

        try:
            self.docs_service.documents().batchUpdate(
                documentId=doc_id, body={"requests": requests}
            ).execute()
            return True
        except Exception as e:
            print(f"이미지 삽입 실패: {e}")
            return False

    def insert_image_after_heading(
        self,
        doc_id: str,
        image_url: str,
        heading_text: str,
        width: int = 400,
    ) -> bool:
        """
        특정 제목 다음에 이미지 삽입

        Args:
            doc_id: 문서 ID
            image_url: 이미지 URL
            heading_text: 제목 텍스트
            width: 이미지 너비 (PT)

        Returns:
            성공 여부
        """
        doc = self.docs_service.documents().get(documentId=doc_id).execute()
        body_content = doc.get("body", {}).get("content", [])

        for i, element in enumerate(body_content):
            if "paragraph" in element:
                para = element["paragraph"]
                para_style = para.get("paragraphStyle", {})
                named_style = para_style.get("namedStyleType", "")

                # 제목인지 확인
                if "HEADING" in named_style:
                    for para_element in para.get("elements", []):
                        text_run = para_element.get("textRun", {})
                        content = text_run.get("content", "").strip()

                        if heading_text in content:
                            # 다음 요소의 시작 위치에 삽입
                            end_index = element.get("endIndex", 0)

                            # 줄바꿈 + 이미지 삽입
                            requests = [
                                {
                                    "insertText": {
                                        "location": {"index": end_index},
                                        "text": "\n",
                                    }
                                },
                                {
                                    "insertInlineImage": {
                                        "location": {"index": end_index + 1},
                                        "uri": image_url,
                                        "objectSize": {
                                            "width": {"magnitude": width, "unit": "PT"}
                                        },
                                    }
                                },
                            ]

                            try:
                                self.docs_service.documents().batchUpdate(
                                    documentId=doc_id, body={"requests": requests}
                                ).execute()
                                return True
                            except Exception as e:
                                print(f"이미지 삽입 실패: {e}")
                                return False

        print(f"제목을 찾을 수 없습니다: {heading_text}")
        return False

    def delete_image(
        self,
        doc_id: str,
        image_id: str,
    ) -> bool:
        """
        문서에서 이미지 삭제

        Args:
            doc_id: 문서 ID
            image_id: 이미지 객체 ID

        Returns:
            성공 여부
        """
        requests = [
            {
                "deleteContentRange": {
                    "range": {
                        "segmentId": "",
                        "startIndex": 0,  # 실제 인덱스로 교체 필요
                        "endIndex": 1,
                    }
                }
            }
        ]

        try:
            self.docs_service.documents().batchUpdate(
                documentId=doc_id, body={"requests": requests}
            ).execute()
            return True
        except Exception as e:
            print(f"이미지 삭제 실패: {e}")
            return False


# 편의 함수
def create_inserter(credentials) -> ImageInserter:
    """ImageInserter 인스턴스 생성"""
    return ImageInserter(credentials)
