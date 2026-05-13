import argparse
import json
from pathlib import Path
from . import OCRExtractor, check_installation


def main():
    parser = argparse.ArgumentParser(
        prog="python -m lib.ocr",
        description="Tesseract OCR CLI - 이미지 텍스트 추출 도구"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # extract 서브커맨드
    extract_parser = subparsers.add_parser(
        "extract",
        help="이미지에서 텍스트 추출"
    )
    extract_parser.add_argument(
        "image_path",
        type=str,
        help="이미지 파일 경로"
    )
    extract_parser.add_argument(
        "--lang",
        type=str,
        default="kor+eng",
        help="언어 코드 (기본값: kor+eng)"
    )
    extract_parser.add_argument(
        "--no-preprocess",
        action="store_true",
        help="전처리 비활성화"
    )
    extract_parser.add_argument(
        "--preset",
        type=str,
        choices=["document", "photo", "screenshot", "handwriting", "table"],
        help="전처리 프리셋"
    )
    extract_parser.add_argument(
        "--output",
        type=str,
        help="출력 파일 경로 (JSON)"
    )
    extract_parser.add_argument(
        "--table",
        action="store_true",
        help="표 감지 및 추출 모드"
    )

    # check 서브커맨드
    check_parser = subparsers.add_parser(
        "check",
        help="Tesseract 설치 확인"
    )

    args = parser.parse_args()

    if args.command == "check":
        info = check_installation()
        print(json.dumps(info, indent=2, ensure_ascii=False))

        if not info["installed"]:
            print("\n설치 방법:")
            print("  scoop install tesseract")
            print("  또는: https://github.com/UB-Mannheim/tesseract/wiki")
            return 1

        return 0

    elif args.command == "extract":
        image_path = Path(args.image_path)

        if not image_path.exists():
            print(f"Error: 파일을 찾을 수 없음: {image_path}")
            return 1

        try:
            extractor = OCRExtractor(image_path, lang=args.lang)

            if args.table:
                # 표 감지 모드
                tables = extractor.detect_tables(preprocess=not args.no_preprocess)

                result_data = {
                    "num_tables": len(tables),
                    "tables": [
                        {
                            "rows": table.rows,
                            "cols": table.cols,
                            "markdown": table.to_markdown(),
                            "csv": table.to_csv(),
                        }
                        for table in tables
                    ]
                }

                if args.output:
                    Path(args.output).write_text(
                        json.dumps(result_data, indent=2, ensure_ascii=False)
                    )
                else:
                    for i, table in enumerate(tables):
                        print(f"\n=== Table {i+1} ({table.rows}x{table.cols}) ===")
                        print(table.to_markdown())

            else:
                # 일반 텍스트 추출 모드
                result = extractor.extract_text(preprocess=not args.no_preprocess)

                if args.output:
                    Path(args.output).write_text(
                        json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
                    )
                else:
                    print(result.text)
                    print(f"\n[Confidence: {result.confidence:.2f}]")
                    print(f"[Processing time: {result.processing_time:.2f}s]")

        except Exception as e:
            print(f"Error: {e}")
            return 1

        return 0


if __name__ == "__main__":
    exit(main())
