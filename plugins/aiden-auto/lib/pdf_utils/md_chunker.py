"""
MD 파일 파서 및 PRD 전용 청킹 전략 구현.
4가지 전략: fixed, hierarchical, semantic, hierarchical+semantic
"""
import re
import warnings
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .prd_models import PRDChunk, PRDChunkResult
from .strategy import (
    estimate_tokens, auto_select_strategy, detect_prd_structure, enrich_chunk_metadata
)


# ──────────────────────────────────────────────
# 블록 타입
# ──────────────────────────────────────────────
class BlockType(Enum):
    HEADING = "heading"
    TABLE = "table"
    CODE_BLOCK = "code_block"
    LIST = "list"
    PARAGRAPH = "paragraph"


@dataclass
class Block:
    type: BlockType
    text: str
    level: int = 0          # HEADING만 사용 (1=H1, 2=H2, 3=H3, 4=H4+)
    is_atomic: bool = False  # TABLE, CODE_BLOCK은 True
    has_table: bool = False
    has_code: bool = False


# ──────────────────────────────────────────────
# MD 파서
# ──────────────────────────────────────────────
class MDParser:
    def parse(self, text: str) -> List[Block]:
        """MD 텍스트를 Block 목록으로 파싱"""
        blocks = []
        lines = text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]

            # 코드블록
            if line.strip().startswith('```'):
                code_lines = [line]
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                if i < len(lines):
                    code_lines.append(lines[i])
                i += 1
                blocks.append(Block(
                    type=BlockType.CODE_BLOCK,
                    text='\n'.join(code_lines),
                    is_atomic=True,
                    has_code=True
                ))
                continue

            # 표: 현재 행이 | 로 시작하고 다음 3행 이내에 구분선 존재
            if line.strip().startswith('|'):
                next_3 = lines[i+1:i+4]
                is_table_start = any(
                    '|---|' in l or '|:---|' in l or '|---:|' in l
                    for l in next_3
                )
                if is_table_start or '|---|' in line:
                    table_lines = []
                    while i < len(lines) and lines[i].strip().startswith('|'):
                        table_lines.append(lines[i])
                        i += 1
                    blocks.append(Block(
                        type=BlockType.TABLE,
                        text='\n'.join(table_lines),
                        is_atomic=True,
                        has_table=True
                    ))
                    continue

            # 헤딩
            heading_match = re.match(r'^(#{1,4})\s+(.*)', line)
            if heading_match:
                level = len(heading_match.group(1))
                blocks.append(Block(
                    type=BlockType.HEADING,
                    text=line,
                    level=level
                ))
                i += 1
                continue

            # 목록
            if re.match(r'^(\s*[-*+]|\s*\d+\.)\s+', line):
                list_lines = []
                while i < len(lines) and (
                    re.match(r'^(\s*[-*+]|\s*\d+\.)\s+', lines[i]) or
                    (lines[i].startswith('  ') and list_lines)
                ):
                    list_lines.append(lines[i])
                    i += 1
                blocks.append(Block(type=BlockType.LIST, text='\n'.join(list_lines)))
                continue

            # 단락
            para_lines = []
            while i < len(lines) and lines[i].strip() and not lines[i].startswith('#') and not lines[i].strip().startswith('|') and not lines[i].strip().startswith('```'):
                para_lines.append(lines[i])
                i += 1
            if para_lines:
                blocks.append(Block(type=BlockType.PARAGRAPH, text='\n'.join(para_lines)))
            else:
                i += 1

        return blocks


# ──────────────────────────────────────────────
# MD 청커
# ──────────────────────────────────────────────
class MDChunker:
    def __init__(
        self,
        strategy: str = "auto",
        max_tokens: int = 8000,
        overlap: int = 400,
        encoding: str = "cl100k_base",
        threshold: int = 60000,
    ):
        self.strategy = strategy
        self.max_tokens = max_tokens
        self.overlap = overlap
        self.encoding = encoding
        self.threshold = threshold
        self.parser = MDParser()

    def _tok(self, text: str) -> int:
        return estimate_tokens(text, self.encoding)

    def _enrich_metadata(self, chunk: PRDChunk) -> None:
        """청크에 메타데이터 주입 (req_ids, priority, doc_type, keywords)"""
        enrich_chunk_metadata(chunk)

    def _link_chunks(self, chunks: List[PRDChunk]) -> List[PRDChunk]:
        """prev_chunk_id / next_chunk_id 연결 + 메타데이터 추출"""
        for i, chunk in enumerate(chunks):
            chunk.prev_chunk_id = chunks[i-1].chunk_id if i > 0 else None
            chunk.next_chunk_id = chunks[i+1].chunk_id if i < len(chunks)-1 else None
            self._enrich_metadata(chunk)
        return chunks

    def chunk_fixed(self, blocks: List[Block]) -> List[PRDChunk]:
        """Fixed-size: 섹션 경계 우선, 원자 블록 보호"""
        chunks = []
        current_texts = []
        current_tokens = 0
        chunk_id = 0

        def flush(current_texts, chunk_id):
            text = '\n'.join(current_texts)
            if text.strip():
                chunks.append(PRDChunk(
                    chunk_id=chunk_id,
                    text=text,
                    token_count=self._tok(text),
                    has_table=any('|---|' in t for t in current_texts),
                    has_code=any('```' in t for t in current_texts),
                    start_char=0, end_char=len(text),
                ))
                return chunk_id + 1
            return chunk_id

        for block in blocks:
            btok = self._tok(block.text)
            # 섹션 경계(HEADING)에서 청크 분리
            if block.type == BlockType.HEADING and current_texts:
                chunk_id = flush(current_texts, chunk_id)
                current_texts = []
                current_tokens = 0

            # 원자 블록이 max_tokens 초과 시 단독 배출
            if block.is_atomic and btok > self.max_tokens:
                if current_texts:
                    chunk_id = flush(current_texts, chunk_id)
                    current_texts = []
                    current_tokens = 0
                warnings.warn(f"원자 블록이 max_tokens({self.max_tokens}) 초과({btok}). 단독 청크로 배출.")
                chunks.append(PRDChunk(
                    chunk_id=chunk_id,
                    text=block.text,
                    token_count=btok,
                    has_table=block.has_table,
                    has_code=block.has_code,
                    is_atomic=True,
                    start_char=0, end_char=len(block.text),
                ))
                chunk_id += 1
                continue

            # 현재 청크 초과 시 분리 후 추가
            if current_tokens + btok > self.max_tokens and current_texts:
                chunk_id = flush(current_texts, chunk_id)
                current_texts = []
                current_tokens = 0

            current_texts.append(block.text)
            current_tokens += btok

        if current_texts:
            flush(current_texts, chunk_id)

        return self._link_chunks(chunks)

    def chunk_hierarchical(self, blocks: List[Block]) -> List[PRDChunk]:
        """Hierarchical Parent-Child: H1→H2→H3 계층 구조 보존"""
        @dataclass
        class Section:
            level: int
            title: str
            parent_path: List[str]
            content_blocks: List[Block] = field(default_factory=list)

            def has_content(self):
                return bool(self.content_blocks)

            def add(self, block):
                self.content_blocks.append(block)

            def add_atomic(self, block):
                self.content_blocks.append(block)

        section_stack = []
        chunks = []
        chunk_id = 0

        def make_chunk(section: Section) -> PRDChunk:
            nonlocal chunk_id
            text = section.title + '\n' + '\n'.join(b.text for b in section.content_blocks)
            tok = self._tok(text)
            c = PRDChunk(
                chunk_id=chunk_id,
                text=text,
                token_count=tok,
                section_path=section.parent_path + [section.title.lstrip('#').strip()],
                level=section.level,
                parent_summary='/'.join(section.parent_path) if section.parent_path else "",
                has_table=any(b.has_table for b in section.content_blocks),
                has_code=any(b.has_code for b in section.content_blocks),
                start_char=0, end_char=len(text),
            )
            chunk_id += 1
            return c

        def flush_remaining(stack):
            for section in stack:
                if section.has_content():
                    chunks.append(make_chunk(section))
            stack.clear()

        for block in blocks:
            if block.type == BlockType.HEADING:
                level = block.level
                # 현재 레벨 이상의 섹션 닫기
                while section_stack and section_stack[-1].level >= level:
                    closed = section_stack.pop()
                    if closed.has_content():
                        chunks.append(make_chunk(closed))

                parent_path = [s.title.lstrip('#').strip() for s in section_stack]
                section_stack.append(Section(level, block.text, parent_path))

            elif block.is_atomic:
                if section_stack:
                    section_stack[-1].add_atomic(block)
                else:
                    # 섹션 없는 원자 블록: 단독 청크
                    tok = self._tok(block.text)
                    c = PRDChunk(
                        chunk_id=chunk_id, text=block.text, token_count=tok,
                        has_table=block.has_table, has_code=block.has_code, is_atomic=True,
                        start_char=0, end_char=len(block.text),
                    )
                    chunk_id += 1
                    chunks.append(c)
            else:
                if section_stack:
                    section_stack[-1].add(block)
                else:
                    # 섹션 없는 단락: Fixed 방식으로 처리
                    tok = self._tok(block.text)
                    chunks.append(PRDChunk(
                        chunk_id=chunk_id, text=block.text, token_count=tok,
                        start_char=0, end_char=len(block.text),
                    ))
                    chunk_id += 1

        flush_remaining(section_stack)

        # 초과 청크 분할 (원자 블록 제외)
        final = []
        for chunk in chunks:
            if chunk.token_count > self.max_tokens and not chunk.is_atomic:
                sub_blocks = [Block(type=BlockType.PARAGRAPH, text=chunk.text)]
                sub_chunks = self.chunk_fixed(sub_blocks)
                for sc in sub_chunks:
                    sc.section_path = chunk.section_path
                    sc.level = chunk.level
                    sc.parent_summary = chunk.parent_summary
                    sc.chunk_id = chunk_id
                    chunk_id += 1
                    final.append(sc)
            else:
                final.append(chunk)

        return self._link_chunks(final)

    def chunk_semantic(self, blocks: List[Block]) -> List[PRDChunk]:
        """Semantic: 표/목록 단위 보존, 요구사항 번호 경계, 빈 줄 경계"""
        chunks = []
        current_texts = []
        current_tokens = 0
        chunk_id = 0
        req_pattern = re.compile(r'^\*\*(R\d+|NR\d+|SC\d+|C\d+)\.')

        def flush():
            nonlocal chunk_id, current_texts, current_tokens
            text = '\n'.join(current_texts)
            if text.strip():
                chunks.append(PRDChunk(
                    chunk_id=chunk_id, text=text, token_count=self._tok(text),
                    has_table=any('|---|' in t for t in current_texts),
                    has_code=any('```' in t for t in current_texts),
                    start_char=0, end_char=len(text),
                ))
                chunk_id += 1
            current_texts = []
            current_tokens = 0

        for block in blocks:
            btok = self._tok(block.text)
            # 요구사항 번호 변경점 = 경계
            if req_pattern.match(block.text.strip()) and current_texts:
                flush()
            # 원자 블록은 단독 청크
            if block.is_atomic:
                if current_texts:
                    flush()
                if btok > self.max_tokens:
                    warnings.warn(f"원자 블록 max_tokens 초과({btok}). 단독 배출.")
                chunks.append(PRDChunk(
                    chunk_id=chunk_id, text=block.text, token_count=btok,
                    has_table=block.has_table, has_code=block.has_code, is_atomic=True,
                    start_char=0, end_char=len(block.text),
                ))
                chunk_id += 1
                continue
            # 초과 시 분리
            if current_tokens + btok > self.max_tokens and current_texts:
                flush()
            current_texts.append(block.text)
            current_tokens += btok

        if current_texts:
            flush()
        return self._link_chunks(chunks)

    def process(self, file_path: str) -> PRDChunkResult:
        """파일 읽기 → 전략 선택 → 청킹 → PRDChunkResult 반환"""
        path = Path(file_path)
        text = path.read_text(encoding='utf-8')
        total_chars = len(text)
        total_tokens = estimate_tokens(text, self.encoding)

        # 전략 결정
        strategy = self.strategy
        if strategy == "auto":
            strategy = auto_select_strategy(file_path, text)

        if strategy == "none":
            # 청킹 불필요: 전체 단일 청크
            chunk = PRDChunk(
                chunk_id=0, text=text, token_count=total_tokens,
                start_char=0, end_char=total_chars,
            )
            return PRDChunkResult(
                source_file=str(path), total_pages=0,
                total_chars=total_chars, total_tokens=total_tokens,
                chunk_count=1, max_tokens_per_chunk=self.max_tokens,
                overlap_tokens=self.overlap, encoding=self.encoding,
                prd_mode=True, strategy="none",
                chunks=[chunk],
            )

        blocks = self.parser.parse(text)
        info = detect_prd_structure(text)

        # 섹션 트리 생성
        section_tree = [
            {"title": b.text.lstrip('#').strip(), "level": b.level}
            for b in blocks if b.type == BlockType.HEADING
        ]

        if strategy == "hierarchical":
            chunks = self.chunk_hierarchical(blocks)
        elif strategy == "semantic":
            chunks = self.chunk_semantic(blocks)
        elif strategy == "hierarchical+semantic":
            # 조합: hierarchical 우선, semantic으로 대형 청크 재분할
            chunks = self.chunk_hierarchical(blocks)
            refined = []
            for chunk in chunks:
                if chunk.token_count > self.max_tokens and not chunk.is_atomic:
                    sub_blocks = self.parser.parse(chunk.text)
                    sub = self.chunk_semantic(sub_blocks)
                    for sc in sub:
                        sc.section_path = chunk.section_path
                        sc.level = chunk.level
                    refined.extend(sub)
                else:
                    refined.append(chunk)
            chunks = self._link_chunks(refined)
        else:  # fixed
            chunks = self.chunk_fixed(blocks)

        return PRDChunkResult(
            source_file=str(path), total_pages=0,
            total_chars=total_chars, total_tokens=total_tokens,
            chunk_count=len(chunks), max_tokens_per_chunk=self.max_tokens,
            overlap_tokens=self.overlap, encoding=self.encoding,
            prd_mode=True, strategy=strategy,
            section_tree=section_tree,
            chunks=chunks,
        )
