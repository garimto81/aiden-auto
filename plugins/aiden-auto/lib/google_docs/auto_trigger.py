"""
자동 트리거 핸들러

키워드 및 파일 패턴 기반 자동 변환 트리거
"""

from pathlib import Path

from .converter import create_google_doc
from .auth import DEFAULT_FOLDER_ID
from .project_registry import get_project_folder_id


class AutoTriggerHandler:
    """자동 트리거 핸들러"""

    TRIGGERS = {
        "keywords": [
            "prd to gdocs",
            "md to docs",
            "--to-gdocs",
            "google docs로",
            "convert to google docs",
            "gdocs",
        ],
        "file_patterns": [
            "tasks/prds/*.md",
            "**/PRD-*.md",
            "**/prd-*.md",
            "docs/prds/*.md",
        ],
    }

    def __init__(self, folder_id: str | None = None):
        """
        Args:
            folder_id: Google Drive 폴더 ID (None이면 기본 폴더)
        """
        try:
            self.folder_id = folder_id or get_project_folder_id(subfolder="documents")
        except Exception:
            self.folder_id = folder_id or DEFAULT_FOLDER_ID

    def should_trigger(
        self,
        user_input: str | None = None,
        file_path: Path | None = None,
    ) -> bool:
        """
        트리거 조건 평가

        Args:
            user_input: 사용자 입력 텍스트
            file_path: 대상 파일 경로

        Returns:
            트리거 여부
        """
        # 키워드 기반 트리거
        if user_input:
            user_lower = user_input.lower()
            if any(kw in user_lower for kw in self.TRIGGERS["keywords"]):
                return True

        # 파일 패턴 기반 트리거
        if file_path:
            file_path = Path(file_path)
            for pattern in self.TRIGGERS["file_patterns"]:
                if file_path.match(pattern):
                    return True

        return False

    def execute(self, target: str | Path) -> str:
        """
        변환 실행 및 URL 반환

        Args:
            target: 변환할 파일 경로 또는 마크다운 텍스트

        Returns:
            생성된 문서 URL

        Raises:
            ValueError: 파일이 존재하지 않거나 읽을 수 없는 경우
            Exception: Google Docs API 에러
        """
        # 파일 경로인 경우
        if isinstance(target, (str, Path)):
            target_path = Path(target)

            if target_path.is_file():
                # 파일 읽기
                content = target_path.read_text(encoding="utf-8")
                title = target_path.stem
            else:
                # 마크다운 텍스트로 간주
                content = str(target)
                title = "Untitled Document"
        else:
            content = str(target)
            title = "Untitled Document"

        # 변환 실행
        print(f"[AutoTrigger] '{title}' 변환 시작...")

        try:
            doc_url = create_google_doc(
                title=title,
                content=content,
                folder_id=self.folder_id,
                include_toc=True,
                use_native_tables=True,
                apply_page_style=True,
            )

            print(f"[AutoTrigger] 완료: {doc_url}")
            return doc_url

        except Exception as e:
            error_msg = f"변환 실패: {type(e).__name__}: {str(e)}"
            print(f"[AutoTrigger] {error_msg}")
            raise

    def suggest_conversion(self, file_path: Path) -> dict:
        """
        변환 제안 생성 (자동 감지용)

        Args:
            file_path: 검사할 파일

        Returns:
            제안 정보 딕셔너리
            {
                'should_convert': bool,
                'reason': str,
                'confidence': float,  # 0.0 ~ 1.0
                'file_path': Path,
            }
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return {
                "should_convert": False,
                "reason": "파일이 존재하지 않습니다",
                "confidence": 0.0,
                "file_path": file_path,
            }

        if not file_path.is_file():
            return {
                "should_convert": False,
                "reason": "파일이 아닙니다",
                "confidence": 0.0,
                "file_path": file_path,
            }

        # 확장자 확인
        if file_path.suffix.lower() != ".md":
            return {
                "should_convert": False,
                "reason": "마크다운 파일이 아닙니다",
                "confidence": 0.0,
                "file_path": file_path,
            }

        # 파일 크기 확인 (너무 크면 패턴 매칭 전에 차단)
        file_size = file_path.stat().st_size
        if file_size > 1_000_000:  # 1MB
            return {
                "should_convert": False,
                "reason": f"파일이 너무 큽니다 ({file_size / 1024 / 1024:.1f} MB)",
                "confidence": 0.0,
                "file_path": file_path,
            }

        # 파일 패턴 매칭
        matched_patterns = []
        for pattern in self.TRIGGERS["file_patterns"]:
            if file_path.match(pattern):
                matched_patterns.append(pattern)

        if matched_patterns:
            # 패턴 매칭 성공
            confidence = 0.9 if "PRD" in file_path.name.upper() else 0.7

            return {
                "should_convert": True,
                "reason": f'파일 패턴 매칭: {", ".join(matched_patterns)}',
                "confidence": confidence,
                "file_path": file_path,
            }

        # 일반 마크다운 파일
        return {
            "should_convert": False,
            "reason": "자동 변환 패턴과 일치하지 않습니다",
            "confidence": 0.3,
            "file_path": file_path,
        }
