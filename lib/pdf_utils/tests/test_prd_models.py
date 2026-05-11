"""PRDChunk, PRDChunkResult 모델 테스트"""
from lib.pdf_utils.prd_models import PRDChunk, PRDChunkResult


class TestPRDChunk:
    def test_to_dict_required_fields(self):
        """to_dict()에 필수 필드(chunk_id, text, token_count) 포함 검증"""
        chunk = PRDChunk(chunk_id=0, text="테스트 텍스트", token_count=5)
        d = chunk.to_dict()
        assert "chunk_id" in d
        assert "text" in d
        assert "token_count" in d
        assert d["chunk_id"] == 0
        assert d["text"] == "테스트 텍스트"
        assert d["token_count"] == 5

    def test_to_dict_all_fields(self):
        """to_dict()에 모든 필드가 포함되어 있는지 검증"""
        chunk = PRDChunk(chunk_id=1, text="내용", token_count=3)
        d = chunk.to_dict()
        expected_keys = {
            "chunk_id", "text", "token_count", "section_path", "level",
            "parent_summary", "prev_chunk_id", "next_chunk_id",
            "has_table", "has_code", "is_atomic", "start_char", "end_char",
            "req_ids", "priority", "doc_type", "keywords",
        }
        assert expected_keys == set(d.keys())

    def test_prev_next_chunk_id_default_none(self):
        """prev_chunk_id, next_chunk_id 기본값이 None인지 검증"""
        chunk = PRDChunk(chunk_id=0, text="텍스트", token_count=2)
        assert chunk.prev_chunk_id is None
        assert chunk.next_chunk_id is None
        d = chunk.to_dict()
        assert d["prev_chunk_id"] is None
        assert d["next_chunk_id"] is None

    def test_section_path_default_empty(self):
        """section_path 기본값이 빈 리스트인지 검증"""
        chunk = PRDChunk(chunk_id=0, text="텍스트", token_count=2)
        assert chunk.section_path == []

    def test_flags_default_false(self):
        """has_table, has_code, is_atomic 기본값 False 검증"""
        chunk = PRDChunk(chunk_id=0, text="텍스트", token_count=2)
        assert chunk.has_table is False
        assert chunk.has_code is False
        assert chunk.is_atomic is False


class TestPRDChunkResult:
    def _make_result(self, chunks=None):
        if chunks is None:
            chunks = [PRDChunk(chunk_id=0, text="텍스트", token_count=2)]
        return PRDChunkResult(
            source_file="test.md",
            total_pages=0,
            total_chars=100,
            total_tokens=50,
            chunk_count=len(chunks),
            max_tokens_per_chunk=8000,
            overlap_tokens=400,
            encoding="cl100k_base",
            prd_mode=True,
            strategy="hierarchical",
            chunks=chunks,
        )

    def test_to_dict_base_fields(self):
        """기존 4개 필드(source_file, total_pages, chunk_count, chunks) 검증"""
        result = self._make_result()
        d = result.to_dict()
        assert "source_file" in d
        assert "total_pages" in d
        assert "chunk_count" in d
        assert "chunks" in d

    def test_to_dict_chunks_serialized(self):
        """chunks가 dict 리스트로 직렬화되는지 검증"""
        result = self._make_result()
        d = result.to_dict()
        assert isinstance(d["chunks"], list)
        assert isinstance(d["chunks"][0], dict)
        assert "chunk_id" in d["chunks"][0]

    def test_to_dict_prd_fields(self):
        """PRD 전용 필드(prd_mode, strategy, section_tree) 포함 검증"""
        result = self._make_result()
        d = result.to_dict()
        assert "prd_mode" in d
        assert "strategy" in d
        assert "section_tree" in d
        assert d["prd_mode"] is True
        assert d["strategy"] == "hierarchical"
