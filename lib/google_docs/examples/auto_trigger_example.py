"""
AutoTriggerHandler 사용 예제

키워드 및 파일 패턴 기반 자동 변환을 시연합니다.
"""

from pathlib import Path
from lib.google_docs import AutoTriggerHandler


def main():
    # AutoTriggerHandler 초기화
    handler = AutoTriggerHandler(folder_id=None)

    print("=" * 60)
    print("예제 1: 키워드 트리거 테스트")
    print("=" * 60)

    test_inputs = [
        "이 파일을 google docs로 변환해주세요",
        "prd to gdocs 변환 필요",
        "--to-gdocs 옵션 사용",
        "일반 텍스트 (트리거 없음)",
    ]

    for user_input in test_inputs:
        should = handler.should_trigger(user_input=user_input)
        print(f"입력: '{user_input}'")
        print(f"트리거: {'✓ YES' if should else '✗ NO'}")
        print()

    print("=" * 60)
    print("예제 2: 파일 패턴 트리거 테스트")
    print("=" * 60)

    test_files = [
        Path("C:/claude/tasks/prds/PRD-0001.md"),
        Path("C:/claude/docs/README.md"),
        Path("C:/claude/tasks/design/design-doc.md"),
    ]

    for file_path in test_files:
        should = handler.should_trigger(file_path=file_path)
        print(f"파일: {file_path}")
        print(f"트리거: {'✓ YES' if should else '✗ NO'}")
        print()

    print("=" * 60)
    print("예제 3: 변환 제안 생성")
    print("=" * 60)

    for file_path in test_files:
        suggestion = handler.suggest_conversion(file_path)
        print(f"파일: {file_path.name}")
        print(f"  변환 권장: {suggestion['should_convert']}")
        print(f"  이유: {suggestion['reason']}")
        print(f"  신뢰도: {suggestion['confidence']:.1%}")
        print()

    print("=" * 60)
    print("예제 4: 실제 변환 실행 (주석 처리됨)")
    print("=" * 60)

    # 실제 변환 실행 예제 (필요 시 주석 해제)
    # file_path = Path("C:/claude/tasks/prds/PRD-0001.md")
    # if file_path.exists():
    #     try:
    #         doc_url = handler.execute(file_path)
    #         print(f"변환 완료: {doc_url}")
    #     except Exception as e:
    #         print(f"변환 실패: {e}")

    print("주석을 해제하여 실제 변환을 테스트할 수 있습니다.")


if __name__ == "__main__":
    main()
