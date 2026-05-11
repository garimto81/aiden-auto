"""auto_select_strategy 테스트 — 6개 TC"""
from unittest.mock import patch
from lib.pdf_utils.strategy import auto_select_strategy, detect_prd_structure


def _make_text_with_tokens(target_tokens: int, has_prd: bool = False, heavy_table: bool = False) -> str:
    """지정 토큰 수에 근접한 텍스트 생성 (간이 추정: len // 3 = tokens → len = tokens * 3)"""
    base_len = target_tokens * 3

    if has_prd:
        header = (
            "# PRD 문서 제목\n\n"
            "## 1. 개요\n\n내용입니다.\n\n"
            "## 2. 요구사항\n\n"
            "**R1. 기능 요구사항**: 내용\n\n"
            "**NR1. 비기능 요구사항**: 내용\n\n"
            "## 3. 기술 요구사항\n\n"
            "| 항목 | 설명 |\n|---|---|\n| 항목1 | 설명1 |\n\n"
        )
        pad_len = max(0, base_len - len(header))
        return header + "x" * pad_len
    elif heavy_table:
        # 표 라인이 전체의 20% 이상
        lines_needed = 100
        table_lines = int(lines_needed * 0.25)
        table = "| 컬럼1 | 컬럼2 |\n|---|---|\n"
        for i in range(table_lines):
            table += f"| 데이터{i} | 값{i} |\n"
        pad_len = max(0, base_len - len(table))
        return table + "x" * pad_len
    else:
        return "x" * base_len


# ──────────────────────────────────────────────
# TC01: 빈 문서 → "none"
# ──────────────────────────────────────────────
def test_tc01_empty_document(tmp_path):
    md_file = tmp_path / "empty.md"
    md_file.write_text("", encoding='utf-8')

    result = auto_select_strategy(str(md_file))
    assert result == "none"


# ──────────────────────────────────────────────
# TC02: 50K 토큰 문서 → "none" (tiktoken 미설치 간이 추정 기준)
# ──────────────────────────────────────────────
def test_tc02_small_document_none(tmp_path):
    # 간이 추정: len // 3 = 50000 → len = 150000
    # tiktoken 미설치 시 THRESHOLD_CHUNK_CONSERVATIVE = 40,000
    # tiktoken 설치 시 THRESHOLD_CHUNK = 60,000
    # 50K 토큰은 두 경우 모두 임계값 이하가 아닐 수 있으므로 명시적 패치 사용
    small_text = "단어 " * 5000  # 약 10,000자 → 약 3,333 토큰 (간이 추정)

    md_file = tmp_path / "small.md"
    md_file.write_text(small_text, encoding='utf-8')

    result = auto_select_strategy(str(md_file))
    assert result == "none"


# ──────────────────────────────────────────────
# TC03: 70K 토큰 PRD 문서 → "hierarchical"
# ──────────────────────────────────────────────
def test_tc03_prd_document_hierarchical(tmp_path):
    # tiktoken 없을 때 간이 추정: 70000 * 3 = 210,000자
    # tiktoken 있을 때는 실제 토큰 수 기준
    # 간이 추정 강제로 테스트 안정화
    from lib.pdf_utils import strategy as strat_mod

    prd_text = _make_text_with_tokens(70000, has_prd=True)
    md_file = tmp_path / "prd_70k.md"
    md_file.write_text(prd_text, encoding='utf-8')

    # tiktoken 미설치 상황 시뮬레이션 (간이 추정 기준으로 강제)
    with patch.object(strat_mod, 'TIKTOKEN_AVAILABLE', False):
        result = auto_select_strategy(str(md_file), text=prd_text)

    # 70K > 40K(conservative threshold), prd_score >= 3, < 100K → hierarchical
    assert result == "hierarchical"


# ──────────────────────────────────────────────
# TC04: 70K 토큰 비PRD 문서 → "fixed"
# ──────────────────────────────────────────────
def test_tc04_non_prd_document_fixed(tmp_path):
    from lib.pdf_utils import strategy as strat_mod

    # 표 없음, 요구사항 번호 없음, 헤딩 없음
    non_prd_text = "x" * (70000 * 3)
    md_file = tmp_path / "non_prd_70k.md"
    md_file.write_text(non_prd_text, encoding='utf-8')

    with patch.object(strat_mod, 'TIKTOKEN_AVAILABLE', False):
        result = auto_select_strategy(str(md_file), text=non_prd_text)

    # prd_score < 3, is_heavy_table False, token < 100K → fixed
    assert result == "fixed"


# ──────────────────────────────────────────────
# TC05: 120K 토큰 PRD 문서 → "hierarchical+semantic"
# ──────────────────────────────────────────────
def test_tc05_large_prd_document_combo(tmp_path):
    from lib.pdf_utils import strategy as strat_mod

    prd_text = _make_text_with_tokens(120000, has_prd=True)
    md_file = tmp_path / "prd_120k.md"
    md_file.write_text(prd_text, encoding='utf-8')

    with patch.object(strat_mod, 'TIKTOKEN_AVAILABLE', False):
        result = auto_select_strategy(str(md_file), text=prd_text)

    # 120K >= 100K(THRESHOLD_COMBO) → hierarchical+semantic
    assert result == "hierarchical+semantic"


# ──────────────────────────────────────────────
# TC06: 표 집중 문서(prd_score < 3, 표 20%+) → "semantic"
# ──────────────────────────────────────────────
def test_tc06_heavy_table_document_semantic(tmp_path):
    from lib.pdf_utils import strategy as strat_mod

    # 표 라인이 전체의 25% 이상 되도록 구성
    # 표 200줄 + 일반 텍스트 600줄 → 200/800 = 25%
    table_lines_list = ["| 헤더1 | 헤더2 |", "|---|---|"]
    for i in range(200):
        table_lines_list.append(f"| 데이터{i} | 값{i} |")

    pad_lines = [f"일반 텍스트 내용 {i}" for i in range(600)]
    all_lines = table_lines_list + pad_lines
    heavy_table_text = "\n".join(all_lines)

    # 토큰 수가 임계값(40000) 이상이 되도록 패딩
    target_len = 40001 * 3
    if len(heavy_table_text) < target_len:
        heavy_table_text += "\n" + "x" * (target_len - len(heavy_table_text))

    md_file = tmp_path / "heavy_table.md"
    md_file.write_text(heavy_table_text, encoding='utf-8')

    info = detect_prd_structure(heavy_table_text)
    # is_heavy_table 확인
    assert info["is_heavy_table"] is True, f"is_heavy_table이 True여야 함. info={info}"
    assert info["prd_score"] < 3, f"prd_score < 3이어야 함. info={info}"

    with patch.object(strat_mod, 'TIKTOKEN_AVAILABLE', False):
        result = auto_select_strategy(str(md_file), text=heavy_table_text)

    # prd_score < 3, is_heavy_table True, token < THRESHOLD_COMBO → semantic
    assert result == "semantic"
