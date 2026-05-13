"""
마크다운 배치 변환 처리기

여러 마크다운 파일을 Google Docs로 병렬 변환합니다.
"""

import asyncio
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from .converter import create_google_doc
from .auth import DEFAULT_FOLDER_ID
from .project_registry import get_project_folder_id


@dataclass
class ConvertResult:
    """변환 결과"""

    source_file: Path
    success: bool
    doc_url: Optional[str] = None
    error: Optional[str] = None


class BatchConverter:
    """배치 변환 처리기"""

    def __init__(self, folder_id: str | None = None, parallel: int = 3):
        """
        Args:
            folder_id: Google Drive 폴더 ID (None이면 기본 폴더)
            parallel: 병렬 처리 수 (기본 3)
        """
        try:
            self.folder_id = folder_id or get_project_folder_id(subfolder="documents")
        except Exception:
            self.folder_id = folder_id or DEFAULT_FOLDER_ID
        self.parallel = parallel
        self._semaphore = asyncio.Semaphore(parallel)

    async def convert_batch(self, files: list[Path]) -> list[ConvertResult]:
        """
        여러 파일 병렬 변환

        Args:
            files: 변환할 마크다운 파일 리스트

        Returns:
            변환 결과 리스트
        """
        if not files:
            return []

        print(
            f"[BatchConverter] {len(files)}개 파일 변환 시작 (병렬도: {self.parallel})"
        )

        tasks = [self._convert_single(file) for file in files]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # 통계 출력
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count

        print(f"[BatchConverter] 완료: 성공 {success_count}, 실패 {fail_count}")

        return results

    async def _convert_single(self, file_path: Path) -> ConvertResult:
        """
        단일 파일 변환 (세마포어로 동시 실행 수 제한)

        Args:
            file_path: 변환할 파일

        Returns:
            변환 결과
        """
        async with self._semaphore:
            try:
                # 파일 읽기
                content = await asyncio.to_thread(self._read_file, file_path)

                # 문서 제목 생성 (파일명 기반)
                title = file_path.stem

                # 변환 실행 (동기 함수를 별도 스레드에서 실행)
                doc_url = await asyncio.to_thread(
                    create_google_doc,
                    title=title,
                    content=content,
                    folder_id=self.folder_id,
                    include_toc=True,
                    use_native_tables=True,
                    apply_page_style=True,
                )

                print(f"  ✓ {file_path.name} → {doc_url}")

                return ConvertResult(
                    source_file=file_path,
                    success=True,
                    doc_url=doc_url,
                )

            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                print(f"  ✗ {file_path.name} - {error_msg}")

                return ConvertResult(
                    source_file=file_path,
                    success=False,
                    error=error_msg,
                )

    def _read_file(self, file_path: Path) -> str:
        """파일 읽기 (UTF-8)"""
        return file_path.read_text(encoding="utf-8")

    def convert_directory(
        self,
        directory: Path,
        pattern: str = "*.md",
        recursive: bool = False,
    ) -> list[ConvertResult]:
        """
        디렉토리 내 모든 파일 변환

        Args:
            directory: 검색할 디렉토리
            pattern: 파일 패턴 (기본: *.md)
            recursive: 재귀 검색 여부

        Returns:
            변환 결과 리스트
        """
        if not directory.is_dir():
            raise ValueError(f"디렉토리가 아닙니다: {directory}")

        # 파일 검색
        if recursive:
            files = list(directory.rglob(pattern))
        else:
            files = list(directory.glob(pattern))

        if not files:
            print(
                f"[BatchConverter] {directory}에서 {pattern} 파일을 찾을 수 없습니다."
            )
            return []

        # 비동기 실행
        return asyncio.run(self.convert_batch(files))
