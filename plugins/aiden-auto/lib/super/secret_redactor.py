"""Secret Redactor — telemetry 저장 전 API key·credential 패턴 제거.

CLAUDE.md Safety Rule "API key prohibited" 준수.
실패 시 telemetry 저장 차단 (privacy guard).
"""
from __future__ import annotations

import re

# 흔한 secret 패턴 (보수적, false positive 허용)
PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Anthropic API key (sk-ant-...) — 8+ chars after prefix to catch test keys too
    (re.compile(r"sk-ant-[a-zA-Z0-9_-]{8,}"), "***ANTHROPIC***"),
    # OpenAI API key
    (re.compile(r"sk-[a-zA-Z0-9]{16,}"), "***OPENAI***"),
    # AWS access key
    (re.compile(r"AKIA[0-9A-Z]{16}"), "***AWS_AKIA***"),
    # AWS secret (길이 40 base64-like — 너무 광범위, opt-in)
    # GitHub PAT (classic + fine-grained)
    (re.compile(r"ghp_[a-zA-Z0-9]{36,}"), "***GITHUB_PAT***"),
    (re.compile(r"github_pat_[a-zA-Z0-9_]{50,}"), "***GITHUB_FINE***"),
    # Slack tokens
    (re.compile(r"xox[baprs]-[a-zA-Z0-9-]{10,}"), "***SLACK***"),
    # Generic Bearer in URL/header
    (re.compile(r"(?i)bearer\s+[a-zA-Z0-9._-]{20,}"), "Bearer ***"),
    # password=value pattern
    (re.compile(r"(?i)(password|passwd|secret|token|apikey)\s*[=:]\s*['\"]?([^\s'\"&]{8,})['\"]?"),
     r"\1=***"),
    # URL credentials user:pass@host
    (re.compile(r"://[^/\s]+:[^@\s]+@"), "://***:***@"),
]


def redact(text: str) -> str:
    """주어진 텍스트의 secret 패턴을 redact.

    실패하면 RuntimeError. telemetry_capture.py가 이 경우 저장을 skip해야 함.
    """
    if not isinstance(text, str):
        raise RuntimeError(f"redact expects str, got {type(text).__name__}")
    out = text
    for pat, repl in PATTERNS:
        out = pat.sub(repl, out)
    return out


def is_likely_secret(text: str) -> bool:
    """text가 secret을 포함할 가능성이 높은지 (heuristic)."""
    return any(pat.search(text) for pat, _ in PATTERNS)


__all__ = ["redact", "is_likely_secret", "PATTERNS"]
