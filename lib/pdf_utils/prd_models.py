from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PRDChunk:
    chunk_id: int
    text: str
    token_count: int
    section_path: list = field(default_factory=list)   # ["문서제목", "2. 요구사항", "기능 요구사항"]
    level: int = 0                                      # 0=문서루트, 1=H1, 2=H2, 3=H3
    parent_summary: str = ""                            # 상위 섹션 요약
    prev_chunk_id: Optional[int] = None
    next_chunk_id: Optional[int] = None
    has_table: bool = False
    has_code: bool = False
    is_atomic: bool = False                             # 분리 불가 원자 블록 여부
    start_char: int = 0
    end_char: int = 0
    req_ids: list = field(default_factory=list)         # regex R\d+, NR\d+, SC\d+ 추출 → ["R001", "R002"]
    priority: str = ""                                  # "must"|"should"|"nice" MoSCoW 키워드 감지
    doc_type: str = ""                                  # "functional"|"non-functional"|"constraint"|"glossary"
    keywords: list = field(default_factory=list)        # 핵심 키워드 (중요한 명사/동사 추출)

    def to_dict(self) -> dict:
        """기존 Chunk.to_dict() 호환 필드 포함"""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "token_count": self.token_count,
            "section_path": self.section_path,
            "level": self.level,
            "parent_summary": self.parent_summary,
            "prev_chunk_id": self.prev_chunk_id,
            "next_chunk_id": self.next_chunk_id,
            "has_table": self.has_table,
            "has_code": self.has_code,
            "is_atomic": self.is_atomic,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "req_ids": self.req_ids,
            "priority": self.priority,
            "doc_type": self.doc_type,
            "keywords": self.keywords,
        }


@dataclass
class PRDChunkResult:
    source_file: str
    total_pages: int           # MD면 0, PDF면 실제 페이지 수
    total_chars: int
    total_tokens: int
    chunk_count: int
    max_tokens_per_chunk: int
    overlap_tokens: int
    encoding: str
    prd_mode: bool
    strategy: str              # "fixed"|"hierarchical"|"semantic"|"hierarchical+semantic"|"none"
    section_tree: list = field(default_factory=list)
    chunks: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """기존 JSON 출력 호환 필드 유지 + PRD 전용 필드"""
        return {
            "source_file": self.source_file,
            "total_pages": self.total_pages,
            "total_chars": self.total_chars,
            "total_tokens": self.total_tokens,
            "chunk_count": self.chunk_count,
            "max_tokens_per_chunk": self.max_tokens_per_chunk,
            "overlap_tokens": self.overlap_tokens,
            "encoding": self.encoding,
            "prd_mode": self.prd_mode,
            "strategy": self.strategy,
            "section_tree": self.section_tree,
            "chunks": [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.chunks],
        }
