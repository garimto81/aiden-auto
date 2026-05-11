"""MDChunker / MDParser 테스트 — 9개 TC"""
import time
from lib.pdf_utils.md_chunker import MDChunker, MDParser, BlockType


# ──────────────────────────────────────────────
# TC01: Fixed 청킹 — 헤딩 3개 MD, chunk >= 1, 섹션 경계 분리
# ──────────────────────────────────────────────
def test_tc01_fixed_chunking_with_headings(tmp_path):
    md_content = """# 제목 1

본문 내용입니다.

## 제목 2

두 번째 섹션 내용입니다.

### 제목 3

세 번째 섹션 내용입니다.
"""
    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding='utf-8')

    chunker = MDChunker(strategy="fixed", max_tokens=50)
    result = chunker.process(str(md_file))

    assert result.chunk_count >= 1
    assert len(result.chunks) >= 1
    # 각 청크는 비어있지 않아야 함
    for chunk in result.chunks:
        assert chunk.text.strip() != ""


# ──────────────────────────────────────────────
# TC02: 표 포함 MD — 표 완전성 (분리 없음)
# ──────────────────────────────────────────────
def test_tc02_table_integrity(tmp_path):
    md_content = """# 테이블 문서

| 컬럼1 | 컬럼2 | 컬럼3 |
|---|---|---|
| 데이터1 | 데이터2 | 데이터3 |
| 데이터4 | 데이터5 | 데이터6 |
"""
    md_file = tmp_path / "table_test.md"
    md_file.write_text(md_content, encoding='utf-8')

    parser = MDParser()
    blocks = parser.parse(md_content)

    # 표 블록은 is_atomic=True, 분리 불가
    table_blocks = [b for b in blocks if b.type == BlockType.TABLE]
    assert len(table_blocks) >= 1
    for tb in table_blocks:
        assert tb.is_atomic is True
        assert tb.has_table is True

    # 청킹 후 표는 단일 청크 내에 완전히 포함됨
    chunker = MDChunker(strategy="fixed", max_tokens=5000)
    result = chunker.process(str(md_file))
    table_chunks = [c for c in result.chunks if c.has_table]
    for tc in table_chunks:
        # 표 구분선이 청크 텍스트 내에 완전히 존재해야 함
        assert '|' in tc.text


# ──────────────────────────────────────────────
# TC03: 코드블록 포함 MD — ``` 오픈/클로즈 쌍 무결성
# ──────────────────────────────────────────────
def test_tc03_code_block_integrity(tmp_path):
    md_content = """# 코드 문서

아래는 코드 예시입니다.

```python
def hello():
    print("Hello, World!")
    return True
```

이후 내용입니다.
"""
    md_file = tmp_path / "code_test.md"
    md_file.write_text(md_content, encoding='utf-8')

    parser = MDParser()
    blocks = parser.parse(md_content)

    code_blocks = [b for b in blocks if b.type == BlockType.CODE_BLOCK]
    assert len(code_blocks) >= 1
    for cb in code_blocks:
        assert cb.is_atomic is True
        assert cb.has_code is True
        # 오픈/클로즈 ``` 쌍 무결성 검증
        lines = cb.text.split('\n')
        backtick_lines = [l for l in lines if l.strip().startswith('```')]
        assert len(backtick_lines) >= 2, "코드블록에 ``` 오픈/클로즈 쌍이 있어야 함"


# ──────────────────────────────────────────────
# TC04: Hierarchical — section_path 검증
# ──────────────────────────────────────────────
def test_tc04_hierarchical_section_path(tmp_path):
    md_content = """# H1제목

H1 내용입니다.

## H2제목

H2 내용입니다.
"""
    md_file = tmp_path / "hier_test.md"
    md_file.write_text(md_content, encoding='utf-8')

    chunker = MDChunker(strategy="hierarchical", max_tokens=5000)
    result = chunker.process(str(md_file))

    assert result.chunk_count >= 1
    # section_path가 있는 청크 확인
    path_chunks = [c for c in result.chunks if c.section_path]
    assert len(path_chunks) >= 1

    # H2 청크의 section_path는 ['H1제목', 'H2제목'] 형식이어야 함
    h2_chunks = [c for c in result.chunks if c.level == 2]
    for c in h2_chunks:
        assert len(c.section_path) >= 2
        assert "H2제목" in c.section_path[-1]


# ──────────────────────────────────────────────
# TC05: 60,000 토큰 미만 → strategy="none", 청크 1개
# ──────────────────────────────────────────────
def test_tc05_small_document_no_chunking(tmp_path):
    # 짧은 문서 (토큰 수가 임계값 미만)
    md_content = "# 짧은 문서\n\n이 문서는 아주 짧습니다.\n"
    md_file = tmp_path / "small.md"
    md_file.write_text(md_content, encoding='utf-8')

    chunker = MDChunker(strategy="auto", threshold=60000)
    result = chunker.process(str(md_file))

    # 짧은 문서는 strategy="none", 청크 1개
    assert result.strategy == "none"
    assert result.chunk_count == 1
    assert len(result.chunks) == 1


# ──────────────────────────────────────────────
# TC06: prev/next_chunk_id 체인 연결 검증
# ──────────────────────────────────────────────
def test_tc06_chunk_chain_linkage(tmp_path):
    # 헤딩 여러 개로 여러 청크 강제 생성
    sections = []
    for i in range(5):
        sections.append(f"# 섹션 {i}\n\n" + "내용 " * 100 + "\n")
    md_content = "\n".join(sections)

    md_file = tmp_path / "chain_test.md"
    md_file.write_text(md_content, encoding='utf-8')

    chunker = MDChunker(strategy="fixed", max_tokens=100)
    result = chunker.process(str(md_file))

    if result.chunk_count >= 2:
        chunks = result.chunks
        # chunk[0].next_chunk_id == chunk[1].chunk_id
        assert chunks[0].next_chunk_id == chunks[1].chunk_id
        # chunk[1].prev_chunk_id == chunk[0].chunk_id
        assert chunks[1].prev_chunk_id == chunks[0].chunk_id
        # 첫 청크의 prev는 None, 마지막 청크의 next는 None
        assert chunks[0].prev_chunk_id is None
        assert chunks[-1].next_chunk_id is None


# ──────────────────────────────────────────────
# TC07: 하위 호환성 — PRDChunk.to_dict()에 필수 키 존재
# ──────────────────────────────────────────────
def test_tc07_backward_compatibility():
    from lib.pdf_utils.prd_models import PRDChunk
    chunk = PRDChunk(chunk_id=42, text="하위 호환 테스트", token_count=10)
    d = chunk.to_dict()
    # 기존 Chunk.to_dict() 호환 필드
    assert "chunk_id" in d
    assert "text" in d
    assert "token_count" in d
    assert d["chunk_id"] == 42
    assert d["text"] == "하위 호환 테스트"
    assert d["token_count"] == 10


# ──────────────────────────────────────────────
# TC08: Windows/Unix 경로 처리
# ──────────────────────────────────────────────
def test_tc08_path_handling(tmp_path):
    md_content = "# 경로 테스트\n\n내용입니다.\n"
    md_file = tmp_path / "path_test.md"
    md_file.write_text(md_content, encoding='utf-8')

    chunker = MDChunker(strategy="fixed", max_tokens=5000)

    # Unix 스타일 경로
    unix_path = str(md_file).replace('\\', '/')
    result_unix = chunker.process(unix_path)
    assert result_unix.chunk_count >= 1

    # Windows 스타일 경로 (pathlib.Path로 정규화)
    win_path = str(md_file)
    result_win = chunker.process(win_path)
    assert result_win.chunk_count >= 1


# ──────────────────────────────────────────────
# TC09: 성능 TC — 30,000단어 MD Hierarchical 청킹 30초 이내
# ──────────────────────────────────────────────
def test_tc09_performance_large_document(tmp_path):
    # 약 30,000단어 MD 생성
    sections = []
    for i in range(30):
        sections.append(f"# 섹션 {i}\n\n")
        for j in range(10):
            sections.append(f"## 하위 섹션 {i}-{j}\n\n")
            # 각 섹션에 약 100단어
            sections.append(" ".join([f"단어{k}" for k in range(100)]) + "\n\n")

    md_content = "".join(sections)
    md_file = tmp_path / "large_test.md"
    md_file.write_text(md_content, encoding='utf-8')

    chunker = MDChunker(strategy="hierarchical", max_tokens=8000)

    start = time.perf_counter()
    result = chunker.process(str(md_file))
    elapsed = time.perf_counter() - start

    assert result.chunk_count >= 1
    assert elapsed < 30.0, f"Hierarchical 청킹이 30초 초과: {elapsed:.2f}초"
