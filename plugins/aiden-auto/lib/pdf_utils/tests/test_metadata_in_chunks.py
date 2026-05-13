"""청크에서 메타데이터 추출 통합 테스트"""
from lib.pdf_utils.md_chunker import MDChunker


def test_chunk_metadata_extraction(tmp_path):
    """청크 생성 시 메타데이터 자동 추출 검증"""
    md_content = """# 요구사항 문서

## 기능 요구사항

**R1. 사용자 로그인** — 시스템은 MUST 사용자 로그인 기능을 제공해야 합니다.
이 기능은 보안 및 인증이 중요합니다.

**R2. 데이터 조회** — 사용자 데이터 조회 및 관리 기능이 필요합니다.

## 비기능 요구사항

**NR1. 응답 시간** — 시스템 응답 시간은 SHOULD 200ms 이하여야 합니다.

## 제약 조건

**C1. 플랫폼** — Windows 10 이상에서만 지원합니다.
"""
    md_file = tmp_path / "requirements.md"
    md_file.write_text(md_content, encoding='utf-8')

    chunker = MDChunker(strategy="hierarchical", max_tokens=1000)
    result = chunker.process(str(md_file))

    # 청크가 생성되어야 함
    assert result.chunk_count > 0

    # 각 청크의 메타데이터 검증
    has_req_ids = False
    has_priority = False
    has_doc_type = False
    has_keywords = False

    for chunk in result.chunks:
        # req_ids 필드 존재
        assert hasattr(chunk, 'req_ids')
        if chunk.req_ids:
            has_req_ids = True

        # priority 필드 존재
        assert hasattr(chunk, 'priority')
        if chunk.priority:
            has_priority = True

        # doc_type 필드 존재
        assert hasattr(chunk, 'doc_type')
        if chunk.doc_type:
            has_doc_type = True

        # keywords 필드 존재
        assert hasattr(chunk, 'keywords')
        if chunk.keywords:
            has_keywords = True

        # to_dict()에 메타데이터 포함
        chunk_dict = chunk.to_dict()
        assert 'req_ids' in chunk_dict
        assert 'priority' in chunk_dict
        assert 'doc_type' in chunk_dict
        assert 'keywords' in chunk_dict

    # 적어도 일부 청크에서 메타데이터가 추출되어야 함
    assert has_req_ids, "적어도 하나의 청크에서 req_ids가 추출되어야 함"
    assert has_priority, "적어도 하나의 청크에서 priority가 추출되어야 함"


def test_req_ids_in_chunks(tmp_path):
    """요구사항 ID 추출 검증"""
    md_content = """# PRD

**R1. 기능1** 설명

**NR2. 성능** 설명

**SC1. 보안** 설명
"""
    md_file = tmp_path / "prd.md"
    md_file.write_text(md_content, encoding='utf-8')

    chunker = MDChunker(strategy="semantic", max_tokens=500)
    result = chunker.process(str(md_file))

    # 최소 하나의 청크에서 R1이 추출되어야 함
    req_ids_found = []
    for chunk in result.chunks:
        req_ids_found.extend(chunk.req_ids)

    assert "R1" in req_ids_found, f"R1이 추출되어야 함. 실제: {req_ids_found}"


def test_priority_extraction_must(tmp_path):
    """MUST 우선순위 추출"""
    md_content = """# 필수 기능

시스템은 MUST 다음을 지원해야 합니다:
- 사용자 인증
- 데이터 보호
"""
    md_file = tmp_path / "must.md"
    md_file.write_text(md_content, encoding='utf-8')

    chunker = MDChunker(strategy="fixed", max_tokens=500)
    result = chunker.process(str(md_file))

    # 최소 하나의 청크에서 우선순위가 추출되어야 함 (must/should/nice 또는 HIGH/MEDIUM/LOW)
    priorities = [c.priority for c in result.chunks if c.priority]
    assert len(priorities) > 0, f"우선순위가 추출되어야 함. 실제: {priorities}"


def test_doc_type_detection(tmp_path):
    """문서 타입 감지 검증"""
    md_content = """# 기능 요구사항

## 기능 요구사항 명세

사용자 로그인 기능이 필요합니다.
"""
    md_file = tmp_path / "functional.md"
    md_file.write_text(md_content, encoding='utf-8')

    chunker = MDChunker(strategy="fixed", max_tokens=500)
    result = chunker.process(str(md_file))

    doc_types = [c.doc_type for c in result.chunks if c.doc_type]
    assert "functional" in doc_types, f"functional 타입이 감지되어야 함. 실제: {doc_types}"


def test_keywords_extraction(tmp_path):
    """키워드 추출 검증"""
    md_content = """# 시스템 설계

## 데이터베이스 설계

데이터베이스는 PostgreSQL을 사용합니다.
API 서버는 Node.js를 기반으로 합니다.
캐싱은 Redis를 사용합니다.
"""
    md_file = tmp_path / "design.md"
    md_file.write_text(md_content, encoding='utf-8')

    chunker = MDChunker(strategy="fixed", max_tokens=500)
    result = chunker.process(str(md_file))

    # 키워드 추출 검증
    keywords_found = []
    for chunk in result.chunks:
        keywords_found.extend(chunk.keywords)

    # 기술 키워드가 포함되어야 함
    assert len(keywords_found) > 0, "키워드가 추출되어야 함"


def test_metadata_serialization(tmp_path):
    """메타데이터 JSON 직렬화 검증"""
    md_content = """# 문서

**R1. 요구사항1** — 설명

**R2. 요구사항2** — 설명

## 비기능 요구사항

**NR1. 성능** — 응답 시간 SHOULD 200ms 이하
"""
    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding='utf-8')

    chunker = MDChunker(strategy="semantic", max_tokens=500)
    result = chunker.process(str(md_file))

    # to_dict() 직렬화 검증
    result_dict = result.to_dict()
    assert "chunks" in result_dict
    assert len(result_dict["chunks"]) > 0

    # 각 청크의 메타데이터가 dict에 포함
    for chunk_dict in result_dict["chunks"]:
        assert isinstance(chunk_dict.get("req_ids"), list)
        assert isinstance(chunk_dict.get("priority"), str)
        assert isinstance(chunk_dict.get("doc_type"), str)
        assert isinstance(chunk_dict.get("keywords"), list)
