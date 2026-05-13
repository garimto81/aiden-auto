import re
from pathlib import Path
from typing import Optional, List

# 토큰 임계값
THRESHOLD_CHUNK = 60_000       # 이 이상 → 청킹 필요
THRESHOLD_CHUNK_CONSERVATIVE = 40_000  # tiktoken 미설치 시 보수적 임계값
THRESHOLD_COMBO = 100_000      # 이 이상 → 조합 전략

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

# Regex 패턴 정의
REQ_ID_PATTERN = re.compile(r'\b(R|NR|SC|C)(\d+)\b')
MOSCOW_PATTERN = re.compile(r'\b(MUST|SHOULD|COULD|WONT|must|should|could|won\'t)\b')
PRIORITY_PATTERN = re.compile(r'\b(HIGH|MEDIUM|LOW|high|medium|low)\b')
DOC_TYPE_KEYWORDS = {
    'non-functional': r'(비기능\s*요구|non-?functional|NFR)',
    'functional': r'(기능\s*요구|functional\s*requirement|FR)',
    'constraint': r'(제약\s*조건|constraint)',
    'glossary': r'(용어\s*정의|glossary)',
}
KEYWORD_PATTERN = re.compile(r'\b[가-힣a-zA-Z]{2,}\b')


def estimate_tokens(text: str, encoding: str = "cl100k_base") -> int:
    if TIKTOKEN_AVAILABLE:
        enc = tiktoken.get_encoding(encoding)
        return len(enc.encode(text))
    else:
        # 간이 추정: 평균 3자 = 1토큰
        return len(text) // 3


def detect_prd_structure(text: str) -> dict:
    lines = text.split('\n')
    heading_count = sum(1 for l in lines if l.startswith('#'))
    h2_count = sum(1 for l in lines if l.startswith('## '))
    has_table = any('|---|' in l or '|:---|' in l or '|---:|' in l for l in lines)
    has_req_numbers = bool(re.search(r'\b(R\d+|NR\d+|SC\d+|C\d+)\b', text))
    table_line_count = sum(1 for l in lines if l.strip().startswith('|'))
    is_heavy_table = table_line_count > len(lines) * 0.2

    prd_score = 0
    if heading_count >= 3:    prd_score += 1
    if has_req_numbers:       prd_score += 2
    if has_table:             prd_score += 1
    if h2_count >= 2:         prd_score += 1

    return {
        "prd_score": prd_score,
        "heading_count": heading_count,
        "has_req_numbers": has_req_numbers,
        "has_table": has_table,
        "is_heavy_table": is_heavy_table,
        "h2_count": h2_count,
    }


def extract_req_ids(text: str) -> List[str]:
    """요구사항 ID 추출 (R1, NR1, SC1, C1 등)"""
    matches = REQ_ID_PATTERN.findall(text)
    req_ids = [f"{prefix}{num}" for prefix, num in matches]
    return list(dict.fromkeys(req_ids))  # 중복 제거 (순서 유지)


def extract_priority(text: str) -> str:
    """MoSCoW 우선순위 추출 (MUST→HIGH, SHOULD→MEDIUM, COULD/WONT→LOW)"""
    text_upper = text.upper()

    if 'MUST' in text_upper:
        return 'HIGH'
    elif 'SHOULD' in text_upper:
        return 'MEDIUM'
    elif 'COULD' in text_upper or "WON'T" in text_upper:
        return 'LOW'

    # PRIORITY_PATTERN으로도 확인
    priority_match = PRIORITY_PATTERN.search(text)
    if priority_match:
        priority_val = priority_match.group(1).upper()
        if priority_val == 'HIGH':
            return 'HIGH'
        elif priority_val == 'MEDIUM':
            return 'MEDIUM'
        elif priority_val == 'LOW':
            return 'LOW'

    return ''


def detect_doc_type(text: str) -> str:
    """문서 타입 감지 (functional, non-functional, constraint, glossary)"""
    for dtype, pattern_str in DOC_TYPE_KEYWORDS.items():
        if re.search(pattern_str, text, re.IGNORECASE):
            return dtype
    return ''


def extract_keywords(text: str, top_n: int = 10) -> List[str]:
    """
    핵심 키워드 추출 (빈도 기반, 한글 + 영문)
    top_n: 반환할 키워드 개수
    """
    # 스톱워드 제외
    stopwords = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'of', 'to', 'for', 'is', 'are', 'be',
        '의', '이', '그', '저', '것', '수', '등', '및', '또는', '그리고', '위해', '경우',
    }

    words = KEYWORD_PATTERN.findall(text)
    # 소문자로 정규화하되, 한글은 그대로
    words = [w.lower() if not re.match(r'^[가-힣]+$', w) else w for w in words]

    # 스톱워드 제거 및 빈도 계산
    word_freq = {}
    for word in words:
        if len(word) >= 2 and word not in stopwords:
            word_freq[word] = word_freq.get(word, 0) + 1

    # 빈도순 정렬 후 top_n 반환
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, freq in sorted_words[:top_n]]


def auto_select_strategy(file_path: str, text: Optional[str] = None) -> str:
    path = Path(file_path)
    if text is None:
        try:
            text = path.read_text(encoding='utf-8')
        except Exception:
            return "fixed"

    token_count = estimate_tokens(text)
    threshold = THRESHOLD_CHUNK if TIKTOKEN_AVAILABLE else THRESHOLD_CHUNK_CONSERVATIVE

    if token_count < threshold:
        return "none"

    info = detect_prd_structure(text)

    if info["prd_score"] >= 3 and token_count < THRESHOLD_COMBO:
        return "hierarchical"
    if info["is_heavy_table"] and info["prd_score"] < 3:
        return "semantic"
    if token_count >= THRESHOLD_COMBO:
        return "hierarchical+semantic"

    return "fixed"


def detect_priority(text: str) -> str:
    """MoSCoW 우선순위 감지 (must/should/nice 반환)"""
    text_lower = text.lower()
    must_keywords = ['must', '필수', '반드시', 'required', 'mandatory']
    should_keywords = ['should', '권장', '가능하면', 'recommended', 'preferred']
    nice_keywords = ['nice', '있으면 좋음', 'optional', 'could', 'may']

    must_count = sum(1 for kw in must_keywords if kw in text_lower)
    should_count = sum(1 for kw in should_keywords if kw in text_lower)
    nice_count = sum(1 for kw in nice_keywords if kw in text_lower)

    if must_count >= should_count and must_count >= nice_count and must_count > 0:
        return "must"
    elif should_count >= nice_count and should_count > 0:
        return "should"
    elif nice_count > 0:
        return "nice"
    return ""


def enrich_chunk_metadata(chunk) -> None:
    """PRDChunk에 Phase A 메타데이터를 in-place로 추가"""
    chunk.req_ids = extract_req_ids(chunk.text)
    chunk.priority = detect_priority(chunk.text)
    chunk.doc_type = detect_doc_type(chunk.text)
    chunk.keywords = extract_keywords(chunk.text)
