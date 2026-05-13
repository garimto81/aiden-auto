"""
Google Docs PRD Converter CLI

마크다운 PRD를 Google Docs로 변환하는 CLI 인터페이스
"""

import argparse
import io
import re
import sys
from pathlib import Path

# Windows 콘솔 UTF-8 인코딩 설정 (이모지 출력 지원)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
from typing import Optional

from .auth import DEFAULT_FOLDER_ID
from .project_registry import get_project_folder_id
from .converter import create_google_doc


def _resolve_folder_id(args_folder: Optional[str] = None, project: Optional[str] = None) -> str:
    """CLI에서 폴더 ID 해석 (--project 우선, --folder 차선, 자동 감지 최종)"""
    if args_folder and args_folder != DEFAULT_FOLDER_ID:
        return args_folder  # 명시적 --folder 지정
    try:
        return get_project_folder_id(project=project, subfolder="documents")
    except Exception:
        return DEFAULT_FOLDER_ID  # fallback


def process_file(
    file_path: Path,
    folder_id: Optional[str] = None,
    include_toc: bool = False,
    use_native_tables: bool = True,
    custom_title: Optional[str] = None,
) -> Optional[str]:
    """
    단일 파일 처리

    Args:
        file_path: 마크다운 파일 경로
        folder_id: Google Drive 폴더 ID
        include_toc: 목차 포함 여부
        use_native_tables: 네이티브 테이블 사용 여부
        custom_title: 커스텀 문서 제목

    Returns:
        str | None: 생성된 문서 URL 또는 실패 시 None
    """
    if not file_path.exists():
        print(f"[FAIL] 파일을 찾을 수 없습니다: {file_path}")
        return None

    content = file_path.read_text(encoding="utf-8")

    # 제목 추출 (첫 번째 H1 또는 파일명)
    if custom_title:
        title = custom_title
    else:
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1) if title_match else file_path.stem

    print(f"\n[FILE] {file_path.name}")
    print(f"       제목: {title}")

    try:
        doc_url = create_google_doc(
            title=title,
            content=content,
            folder_id=folder_id,
            include_toc=include_toc,
            use_native_tables=use_native_tables,
            base_path=str(file_path),  # 이미지 상대 경로 해석용
        )
        print(f"[OK] {doc_url}")
        return doc_url
    except Exception as e:
        print(f"[FAIL] {e}")
        return None


def main():
    """CLI 메인 함수"""
    parser = argparse.ArgumentParser(
        prog="python -m lib.google_docs",
        description="PRD 마크다운을 Google Docs 네이티브 형식으로 변환",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 단일 파일 변환 (새 문서 생성)
  python -m lib.google_docs convert file.md

  # 기존 문서 업데이트 (--doc-id 옵션 사용)
  python -m lib.google_docs convert file.md --doc-id 1Y_GmF6xxxxx

  # 커스텀 제목으로 변환
  python -m lib.google_docs convert file.md --title "My PRD"

  # 목차 포함
  python -m lib.google_docs convert file.md --toc

  # 기존 문서 업데이트 + 목차 포함
  python -m lib.google_docs convert file.md --doc-id 1Y_GmF6xxxxx --toc

  # 네이티브 테이블 비활성화 (기본값: 네이티브 테이블 사용)
  python -m lib.google_docs convert file.md --no-native-tables

  # 배치 변환
  python -m lib.google_docs batch tasks/prds/*.md

  # 폴더에 문서 목록 조회
  python -m lib.google_docs list

  # [레거시] update 명령도 계속 사용 가능
  python -m lib.google_docs update 1Y_GmF6xxxxx file.md
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="명령")

    # convert 명령
    convert_parser = subparsers.add_parser(
        "convert", help="마크다운을 Google Docs로 변환 (신규 생성 또는 기존 문서 업데이트)"
    )
    convert_parser.add_argument("file", help="마크다운 파일 경로")
    convert_parser.add_argument("--title", "-t", help="문서 제목 (기본: 파일에서 추출)")
    convert_parser.add_argument(
        "--doc-id",
        "-d",
        help="기존 Google Docs 문서 ID (지정 시 해당 문서를 업데이트, 미지정 시 새 문서 생성)",
    )
    convert_parser.add_argument(
        "--project", "-p", help="프로젝트 이름 (예: WSOPTV, EBS, 지지프로덕션, 브로드스튜디오)"
    )
    convert_parser.add_argument(
        "--folder",
        "-f",
        default=DEFAULT_FOLDER_ID,
        help="Google Drive 폴더 ID (기본: 프로젝트 자동 감지)",
    )
    convert_parser.add_argument("--toc", action="store_true", help="목차 포함")
    convert_parser.add_argument(
        "--no-native-tables",
        dest="native_tables",
        action="store_false",
        help="네이티브 테이블 비활성화 (기본: 네이티브 테이블 사용)",
    )
    convert_parser.set_defaults(native_tables=True)
    convert_parser.add_argument(
        "--no-folder", action="store_true", help="폴더 이동 없이 내 드라이브에 생성"
    )

    # batch 명령
    batch_parser = subparsers.add_parser("batch", help="여러 파일 배치 변환")
    batch_parser.add_argument(
        "files", nargs="+", help="마크다운 파일들 (glob 패턴 지원)"
    )
    batch_parser.add_argument(
        "--project", "-p", help="프로젝트 이름"
    )
    batch_parser.add_argument(
        "--folder", "-f", default=DEFAULT_FOLDER_ID, help="Google Drive 폴더 ID"
    )
    batch_parser.add_argument("--toc", action="store_true", help="목차 포함")
    batch_parser.add_argument(
        "--no-native-tables",
        dest="native_tables",
        action="store_false",
        help="네이티브 테이블 비활성화 (기본: 네이티브 테이블 사용)",
    )
    batch_parser.set_defaults(native_tables=True)

    # update 명령 (기존 문서 내용 교체)
    update_parser = subparsers.add_parser(
        "update", help="기존 Google Docs 문서 내용을 교체 (ID 유지)"
    )
    update_parser.add_argument("doc_id", help="Google Docs 문서 ID")
    update_parser.add_argument("file", help="마크다운 파일 경로")
    update_parser.add_argument("--toc", action="store_true", help="목차 포함")
    update_parser.add_argument(
        "--no-native-tables",
        dest="native_tables",
        action="store_false",
        help="네이티브 테이블 비활성화",
    )
    update_parser.set_defaults(native_tables=True)

    # list 명령
    list_parser = subparsers.add_parser("list", help="폴더의 문서 목록 조회")
    list_parser.add_argument(
        "--folder", "-f", default=DEFAULT_FOLDER_ID, help="Google Drive 폴더 ID"
    )

    # sheets 명령
    sheets_parser = subparsers.add_parser(
        "sheets", help="Google Sheets 데이터 읽기"
    )
    sheets_parser.add_argument(
        "url", help="Google Sheets URL 또는 Spreadsheet ID"
    )
    sheets_parser.add_argument(
        "--range", "-r", default=None, help="A1 표기법 범위 (예: 'Sheet1!A1:Z100')"
    )
    sheets_parser.add_argument(
        "--format", "-fmt", choices=["table", "json", "raw"], default="table",
        help="출력 형식 (기본: table)"
    )
    sheets_parser.add_argument(
        "--max-rows", type=int, default=50, help="최대 출력 행 수 (기본: 50)"
    )
    sheets_parser.add_argument(
        "--list-sheets", action="store_true", help="시트 목록만 조회"
    )

    # drive 명령 (폴더 정리)
    drive_parser = subparsers.add_parser(
        "drive", help="Google Drive 폴더 정리 및 관리"
    )
    drive_subparsers = drive_parser.add_subparsers(dest="drive_command", help="Drive 명령")

    # drive status
    drive_status_parser = drive_subparsers.add_parser("status", help="현재 상태 분석")
    drive_status_parser.add_argument(
        "--folder", "-f", default=DEFAULT_FOLDER_ID, help="대상 폴더 ID"
    )
    drive_status_parser.add_argument(
        "--json", action="store_true", help="JSON 형식 출력"
    )

    # drive duplicates
    drive_dup_parser = drive_subparsers.add_parser("duplicates", help="중복 파일 분석")
    drive_dup_parser.add_argument(
        "--folder", "-f", default=DEFAULT_FOLDER_ID, help="대상 폴더 ID"
    )
    drive_dup_parser.add_argument(
        "--delete", action="store_true", help="중복 파일 삭제 (기본: dry-run)"
    )
    drive_dup_parser.add_argument(
        "--json", action="store_true", help="JSON 형식 출력"
    )

    # drive init
    drive_init_parser = drive_subparsers.add_parser("init", help="폴더 구조 생성")
    drive_init_parser.add_argument(
        "--folder", "-f", default=DEFAULT_FOLDER_ID, help="대상 폴더 ID"
    )

    # drive audit
    drive_audit_parser = drive_subparsers.add_parser("audit", help="폴더 구조 감사 및 교정")
    drive_audit_parser.add_argument(
        "--fix", action="store_true", help="교정 계획 생성 (dry-run)"
    )
    drive_audit_parser.add_argument(
        "--apply", action="store_true", help="교정 실제 적용 (--fix와 함께 사용)"
    )
    drive_audit_parser.add_argument(
        "--json", action="store_true", help="JSON 형식 출력"
    )

    # drive organize
    drive_org_parser = drive_subparsers.add_parser("organize", help="파일 자동 정리")
    drive_org_parser.add_argument(
        "--folder", "-f", default=DEFAULT_FOLDER_ID, help="대상 폴더 ID"
    )
    drive_org_parser.add_argument(
        "--dry-run", action="store_true", default=True, help="미리보기 (기본)"
    )
    drive_org_parser.add_argument(
        "--execute", action="store_true", help="실제 실행"
    )
    drive_org_parser.add_argument(
        "--json", action="store_true", help="JSON 형식 출력"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    print("=" * 60)
    print("Google Docs PRD Converter")
    print("=" * 60)

    if args.command == "convert":
        folder_id = None if args.no_folder else _resolve_folder_id(args.folder, getattr(args, 'project', None))
        use_native = args.native_tables

        file_path = Path(args.file)
        if not file_path.is_absolute():
            file_path = Path.cwd() / file_path

        # --doc-id 옵션이 있으면 기존 문서 업데이트, 없으면 새 문서 생성
        if args.doc_id:
            from .converter import update_google_doc

            if not file_path.exists():
                print(f"[FAIL] 파일을 찾을 수 없습니다: {file_path}")
                sys.exit(1)

            content = file_path.read_text(encoding="utf-8")

            print(f"\n[FILE] {file_path.name}")
            print(f"[DOC]  {args.doc_id} (업데이트 모드)")

            try:
                result = update_google_doc(
                    doc_id=args.doc_id,
                    content=content,
                    include_toc=args.toc,
                    use_native_tables=use_native,
                    base_path=str(file_path),
                )
                print(f"[OK] {result}")
                print("\n" + "=" * 60)
                print(f"[SUCCESS] 문서 업데이트 완료: {result}")
            except Exception as e:
                print(f"[FAIL] {e}")
                import traceback
                traceback.print_exc()
                sys.exit(1)
        else:
            result = process_file(
                file_path=file_path,
                folder_id=folder_id,
                include_toc=args.toc,
                use_native_tables=use_native,
                custom_title=args.title,
            )

            print("\n" + "=" * 60)
            if result:
                print(f"[SUCCESS] 문서 생성 완료: {result}")
            else:
                print("[FAILED] 문서 생성 실패")
                sys.exit(1)

    elif args.command == "batch":
        use_native = args.native_tables

        # 파일 목록 수집
        files = []
        for pattern in args.files:
            path = Path(pattern)
            if "*" in pattern:
                # glob 패턴
                if path.is_absolute():
                    files.extend(path.parent.glob(path.name))
                else:
                    files.extend(Path.cwd().glob(pattern))
            else:
                if not path.is_absolute():
                    path = Path.cwd() / path
                files.append(path)

        batch_folder = _resolve_folder_id(args.folder, getattr(args, 'project', None))
        print(f"파일 수: {len(files)}")
        print(f"폴더 ID: {batch_folder}")
        print(f"테이블: {'네이티브' if use_native else '텍스트'}")
        print("=" * 60)

        results = []
        for file_path in files:
            result = process_file(
                file_path=file_path,
                folder_id=batch_folder,
                include_toc=args.toc,
                use_native_tables=use_native,
            )
            results.append((file_path, result))

        # 결과 요약
        print("\n" + "=" * 60)
        print("결과 요약")
        print("=" * 60)

        success_count = sum(1 for _, url in results if url)
        print(f"성공: {success_count}/{len(results)}")

        for file_path, url in results:
            status = "[OK]" if url else "[FAIL]"
            print(f"  {status} {file_path.name}")
            if url:
                print(f"       {url}")

    elif args.command == "update":
        from .converter import update_google_doc

        file_path = Path(args.file)
        if not file_path.is_absolute():
            file_path = Path.cwd() / file_path

        if not file_path.exists():
            print(f"[FAIL] 파일을 찾을 수 없습니다: {file_path}")
            sys.exit(1)

        content = file_path.read_text(encoding="utf-8")

        print(f"\n[FILE] {file_path.name}")
        print(f"[DOC]  {args.doc_id}")

        try:
            doc_url = update_google_doc(
                doc_id=args.doc_id,
                content=content,
                include_toc=args.toc,
                use_native_tables=args.native_tables,
                base_path=str(file_path),
            )
            print(f"[OK] {doc_url}")
            print("\n" + "=" * 60)
            print(f"[SUCCESS] 문서 업데이트 완료: {doc_url}")
        except Exception as e:
            print(f"[FAIL] {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    elif args.command == "list":
        from googleapiclient.discovery import build
        from .auth import get_credentials

        creds = get_credentials()
        drive_service = build("drive", "v3", credentials=creds)

        query = f"'{args.folder}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false"

        results = (
            drive_service.files()
            .list(
                q=query,
                pageSize=50,
                fields="files(id, name, modifiedTime, webViewLink)",
            )
            .execute()
        )

        files = results.get("files", [])

        print(f"\nDocument List ({len(files)}):")
        print("-" * 60)
        for f in files:
            print(f"  - {f['name']}")
            print(f"    {f['webViewLink']}")
            print()

    elif args.command == "sheets":
        from .sheets import SheetsClient, parse_sheet_url
        import json as json_module

        client = SheetsClient()

        # URL인지 ID인지 판단
        url_or_id = args.url
        if url_or_id.startswith("http"):
            parsed = parse_sheet_url(url_or_id)
            spreadsheet_id = parsed["spreadsheet_id"]
        else:
            spreadsheet_id = url_or_id

        if args.list_sheets:
            sheets_list = client.list_sheets(spreadsheet_id)
            print(f"\n시트 목록 ({len(sheets_list)}개):")
            print("-" * 60)
            for s in sheets_list:
                print(f"  - {s['title']} (gid={s['sheetId']}, {s['rowCount']}x{s['columnCount']})")
        else:
            if args.range:
                result = client.read_from_url(url_or_id, range_notation=args.range)
            else:
                result = client.read_from_url(url_or_id)

            print(f"\n제목: {result['title']}")
            print(f"시트: {result['sheet_name']}")
            print(f"크기: {result['rows']}행 x {result['cols']}열")
            print("-" * 60)

            if args.format == "table":
                print(client.to_markdown_table(result["data"], max_rows=args.max_rows))
            elif args.format == "json":
                print(client.to_json(result["data"], max_rows=args.max_rows))
            elif args.format == "raw":
                print(json_module.dumps(result["data"][:args.max_rows + 1], indent=2, ensure_ascii=False))

    elif args.command == "drive":
        from .drive_organizer import DriveOrganizer, print_status, print_duplicates
        import json as json_module

        if not args.drive_command:
            drive_parser.print_help()
            return

        if args.drive_command == "audit":
            from .drive_guardian import DriveGuardian, print_audit_report, print_fix_plan

            guardian = DriveGuardian()
            report = guardian.audit()

            if args.json:
                output = {
                    "total_root_items": report.total_root_items,
                    "is_clean": report.is_clean,
                    "critical": report.critical_count,
                    "warning": report.warning_count,
                    "info": report.info_count,
                    "project_status": report.project_status,
                    "violations": [
                        {
                            "severity": v.severity.value,
                            "category": v.category,
                            "message": v.message,
                            "file_name": v.file_name,
                            "suggested_action": v.suggested_action,
                        }
                        for v in report.violations
                    ],
                }
                print(json_module.dumps(output, indent=2, ensure_ascii=False))
            else:
                print_audit_report(report)

            if args.fix:
                plan = guardian.generate_fix_plan(report)
                if not plan.actions:
                    print("\nNo fixes needed.")
                else:
                    print_fix_plan(plan)

                    if args.apply:
                        print("\nApplying fixes...")
                        result = guardian.apply_fixes(plan, dry_run=False)
                        print(f"Applied: {len(result['applied'])}")
                        if result['errors']:
                            print(f"Errors: {len(result['errors'])}")
                            for err in result['errors'][:5]:
                                print(f"  - {err['file']}: {err['error']}")
                    else:
                        print("\nTo apply fixes, run:")
                        print("  python -m lib.google_docs drive audit --fix --apply")

        else:
            # status, duplicates, init, organize는 DriveOrganizer 사용
            organizer = DriveOrganizer(args.folder)

            if args.drive_command == "status":
                status = organizer.get_status()
                if args.json:
                    print(json_module.dumps(status, indent=2, ensure_ascii=False))
                else:
                    print_status(status)

            elif args.drive_command == "duplicates":
                if args.delete:
                    result = organizer.delete_duplicates(dry_run=False)
                    if args.json:
                        print(json_module.dumps(result, indent=2, ensure_ascii=False))
                    else:
                        print(f"\nDeleted {len(result['deleted'])} duplicate files")
                        print(f"Errors: {len(result['errors'])}")
                        if result['errors']:
                            for err in result['errors'][:5]:
                                print(f"  - {err['name']}: {err['error']}")
                else:
                    duplicates = organizer.find_duplicates()
                    if args.json:
                        output = [
                            {
                                "name": d.name,
                                "count": d.count,
                                "keep": d.keep.id if d.keep else None,
                                "to_delete": [f.id for f in d.to_delete]
                            }
                            for d in duplicates
                        ]
                        print(json_module.dumps(output, indent=2, ensure_ascii=False))
                    else:
                        print_duplicates(duplicates)
                        print("\nTo delete duplicates, run:")
                        print("  python -m lib.google_docs drive duplicates --delete")

            elif args.drive_command == "init":
                print("\nCreating folder structure...")
                created = organizer.create_folder_structure()
                print(f"Created {len(created)} folders:")
                for path, folder_id in created.items():
                    print(f"  - {path}: {folder_id[:15]}...")
                print("\n[OK] Folder structure created")

            elif args.drive_command == "organize":
                dry_run = not args.execute
                result = organizer.organize_files(dry_run=dry_run)

                if args.json:
                    print(json_module.dumps(result, indent=2, ensure_ascii=False))
                else:
                    mode = "DRY-RUN" if dry_run else "EXECUTED"
                    print(f"\nFile Organization ({mode})")
                    print("=" * 60)
                    print(f"Total files: {result['total_files']}")
                    print(f"Classified: {result['classified']}")
                    print(f"Unclassified: {result['unclassified']}")
                    print()

                    if result['moved']:
                        print("Files to move:" if dry_run else "Files moved:")
                        for item in result['moved'][:20]:
                            print(f"  - {item['name']} -> {item['target']}")
                        if len(result['moved']) > 20:
                            print(f"  ... and {len(result['moved']) - 20} more")

                    if result['errors']:
                        print(f"\nErrors: {len(result['errors'])}")
                        for err in result['errors'][:5]:
                            print(f"  - {err['name']}: {err['error']}")

                    if dry_run:
                        print("\nTo execute, run:")
                        print("  python -m lib.google_docs drive organize --execute")

    print("=" * 60)


if __name__ == "__main__":
    main()
