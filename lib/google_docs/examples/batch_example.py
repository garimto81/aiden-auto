"""
BatchConverter 사용 예제

여러 마크다운 파일을 Google Docs로 일괄 변환합니다.
"""

from pathlib import Path
from lib.google_docs import BatchConverter


def main():
    # BatchConverter 초기화
    converter = BatchConverter(
        folder_id=None,  # 기본 폴더 사용
        parallel=3,  # 동시 3개씩 처리
    )

    # 예제 1: 파일 리스트 변환
    files = [
        Path("C:/claude/tasks/prds/PRD-0001.md"),
        Path("C:/claude/tasks/prds/PRD-0002.md"),
        Path("C:/claude/docs/README.md"),
    ]

    print("=" * 60)
    print("예제 1: 파일 리스트 변환")
    print("=" * 60)

    # 변환 실행 (비동기 실행은 내부에서 처리됨)
    results = converter.convert_batch_sync(files)

    # 결과 출력
    for result in results:
        if result.success:
            print(f"✓ {result.source_file.name}")
            print(f"  URL: {result.doc_url}")
        else:
            print(f"✗ {result.source_file.name}")
            print(f"  Error: {result.error}")

    print()

    # 예제 2: 디렉토리 변환
    print("=" * 60)
    print("예제 2: 디렉토리 변환")
    print("=" * 60)

    directory = Path("C:/claude/tasks/prds")
    results = converter.convert_directory(
        directory=directory,
        pattern="*.md",
        recursive=False,
    )

    # 통계 출력
    success_count = sum(1 for r in results if r.success)
    print(
        f"\n총 {len(results)}개 파일 처리: 성공 {success_count}, 실패 {len(results) - success_count}"
    )


if __name__ == "__main__":
    main()
