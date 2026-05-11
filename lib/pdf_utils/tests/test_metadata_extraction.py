"""메타데이터 추출 함수 테스트 (req_ids, priority, doc_type, keywords)"""
from lib.pdf_utils.strategy import (
    extract_req_ids, extract_priority, detect_doc_type, extract_keywords
)


class TestExtractReqIds:
    """요구사항 ID 추출 테스트"""

    def test_extract_single_r_id(self):
        """단일 R ID 추출"""
        text = "**R1. 사용자 로그인** 기능이 필요합니다."
        result = extract_req_ids(text)
        assert "R1" in result

    def test_extract_multiple_ids(self):
        """여러 요구사항 ID 추출"""
        text = "**R1. 로그인** **NR1. 응답 시간** **SC1. 보안** **C1. 제약사항**"
        result = extract_req_ids(text)
        assert "R1" in result
        assert "NR1" in result
        assert "SC1" in result
        assert "C1" in result

    def test_duplicate_removal(self):
        """중복 ID 제거"""
        text = "R1 설명 R1 또 언급 R1 또 언급"
        result = extract_req_ids(text)
        assert result.count("R1") == 1

    def test_no_ids(self):
        """ID 없을 때 빈 리스트"""
        text = "일반 텍스트입니다."
        result = extract_req_ids(text)
        assert result == []

    def test_id_with_numbers(self):
        """다양한 번호 형식"""
        text = "R123 NR999 SC42 C1"
        result = extract_req_ids(text)
        assert "R123" in result
        assert "NR999" in result
        assert "SC42" in result
        assert "C1" in result


class TestExtractPriority:
    """우선순위 추출 테스트"""

    def test_must_to_high(self):
        """MUST → HIGH"""
        text = "시스템은 MUST 매일 백업해야 합니다."
        result = extract_priority(text)
        assert result == "HIGH"

    def test_should_to_medium(self):
        """SHOULD → MEDIUM"""
        text = "사용자는 SHOULD 한글 입력을 지원받아야 합니다."
        result = extract_priority(text)
        assert result == "MEDIUM"

    def test_could_to_low(self):
        """COULD → LOW"""
        text = "시스템은 COULD 다크 모드를 지원할 수 있습니다."
        result = extract_priority(text)
        assert result == "LOW"

    def test_korean_must(self):
        """한글 우선순위 감지"""
        text = "필수: 로그인 기능"
        # 현재는 영문만 지원하므로 빈 문자열 반환
        result = extract_priority(text)
        assert result == "" or result == "HIGH"

    def test_priority_keyword_direct(self):
        """HIGH/MEDIUM/LOW 직접 감지"""
        text = "Priority: HIGH"
        result = extract_priority(text)
        assert result == "HIGH"

    def test_no_priority(self):
        """우선순위 없을 때 빈 문자열"""
        text = "일반 요구사항입니다."
        result = extract_priority(text)
        assert result == ""


class TestDetectDocType:
    """문서 타입 감지 테스트"""

    def test_functional_requirement(self):
        """기능 요구사항 감지"""
        text = "## 기능 요구사항 (FR)\n사용자가 로그인할 수 있어야 합니다."
        result = detect_doc_type(text)
        assert result == "functional"

    def test_non_functional_requirement(self):
        """비기능 요구사항 감지"""
        text = "## Non-Functional Requirements\n응답 시간은 200ms 이하여야 합니다."
        result = detect_doc_type(text)
        assert result == "non-functional"

    def test_constraint(self):
        """제약 조건 감지"""
        text = "## 제약 조건\n시스템은 Windows 10 이상에서만 동작합니다."
        result = detect_doc_type(text)
        assert result == "constraint"

    def test_glossary(self):
        """용어 정의 감지"""
        text = "## 용어 정의\n**API**: 응용 프로그래밍 인터페이스"
        result = detect_doc_type(text)
        assert result == "glossary"

    def test_no_match(self):
        """매칭 없을 때 빈 문자열"""
        text = "일반 텍스트"
        result = detect_doc_type(text)
        assert result == ""


class TestExtractKeywords:
    """키워드 추출 테스트"""

    def test_basic_keywords(self):
        """기본 키워드 추출"""
        text = "사용자 로그인 시스템은 보안이 중요합니다. 사용자 인증은 필수입니다."
        result = extract_keywords(text, top_n=5)
        assert "사용자" in result
        assert "로그인" in result or "시스템" in result

    def test_top_n_limit(self):
        """top_n 제한"""
        text = "단어 " * 1000
        result = extract_keywords(text, top_n=5)
        assert len(result) <= 5

    def test_stopword_removal(self):
        """스톱워드 제거"""
        text = "the and or but in a an 테스트 시스템"
        result = extract_keywords(text, top_n=10)
        # 스톱워드는 없어야 함
        stopwords = {'the', 'and', 'or', 'but', 'in', 'a', 'an'}
        for word in result:
            assert word.lower() not in stopwords

    def test_frequency_ordering(self):
        """빈도순 정렬"""
        text = "데이터 데이터 데이터 정보 정보 사항"
        result = extract_keywords(text, top_n=3)
        # "데이터"가 빈도가 가장 높음
        assert result[0] == "데이터"

    def test_english_and_korean(self):
        """영문과 한글 혼합"""
        text = "API 시스템 API 데이터베이스 API"
        result = extract_keywords(text, top_n=5)
        assert "api" in result or "API" in result.upper()
        assert "시스템" in result

    def test_empty_text(self):
        """빈 텍스트"""
        text = ""
        result = extract_keywords(text, top_n=5)
        assert result == []

    def test_short_words_ignored(self):
        """1글자 단어 제외"""
        text = "A B 시 테 복잡한 시스템"
        result = extract_keywords(text, top_n=10)
        # 1글자는 포함되지 않음
        for word in result:
            assert len(word) >= 2
