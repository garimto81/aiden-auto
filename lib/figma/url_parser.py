#!/usr/bin/env python3
"""Figma URL parser — extract file_key and node_id from Figma URLs.

Supports all Figma URL formats:
  - Design:  figma.com/design/:fileKey/:fileName?node-id=X-Y
  - File:    figma.com/file/:fileKey/:fileName?node-id=X-Y
  - Branch:  figma.com/design/:fileKey/branch/:branchKey/:fileName
  - Board:   figma.com/board/:fileKey/:fileName?node-id=X-Y  (FigJam)
  - Make:    figma.com/make/:makeFileKey/:makeFileName

Usage:
    python url_parser.py "https://www.figma.com/design/ABC123/MyFile?node-id=1-2"
    python url_parser.py "https://figma.com/design/KEY/branch/BRANCH_KEY/Name"
    python url_parser.py "https://figma.com/board/KEY/Name?node-id=1-2"
    python url_parser.py "https://figma.com/make/KEY/Name"
"""

import json
import re
import sys
from urllib.parse import parse_qs, urlparse

sys.stdout.reconfigure(encoding="utf-8")

# Pattern: /design|file/<key>/branch/<branchKey>/<name>
_BRANCH_RE = re.compile(
    r"^/(?:design|file)/([^/]+)/branch/([^/]+)(?:/([^/?]*))?"
)
# Pattern: /design|file/<key>/<name>
_DESIGN_RE = re.compile(r"^/(?:design|file)/([^/]+)(?:/([^/?]*))?")
# Pattern: /board/<key>/<name>  (FigJam)
_BOARD_RE = re.compile(r"^/board/([^/]+)(?:/([^/?]*))?")
# Pattern: /make/<key>/<name>
_MAKE_RE = re.compile(r"^/make/([^/]+)(?:/([^/?]*))?")


def parse_figma_url(url: str) -> dict:
    """Extract file_key, node_id, file_name, and url_type from a Figma URL.

    Args:
        url: A Figma URL (any supported format)

    Returns:
        {
            "file_key": str,
            "node_id": str | None,
            "file_name": str | None,
            "url_type": "design" | "branch" | "board" | "make",
        }

    Raises:
        ValueError: If the URL is not a valid Figma URL.
    """
    parsed = urlparse(url)
    if not parsed.hostname or "figma.com" not in parsed.hostname:
        raise ValueError(f"Not a Figma URL: {url}")

    qs = parse_qs(parsed.query)
    node_id_raw = qs.get("node-id", [None])[0]
    node_id = node_id_raw.replace("-", ":") if node_id_raw else None

    # Branch URL (must check before design — more specific path)
    match = _BRANCH_RE.match(parsed.path)
    if match:
        return {
            "file_key": match.group(2),  # branchKey as fileKey per MCP spec
            "node_id": node_id,
            "file_name": match.group(3) or None,
            "url_type": "branch",
        }

    # Board URL (FigJam)
    match = _BOARD_RE.match(parsed.path)
    if match:
        return {
            "file_key": match.group(1),
            "node_id": node_id,
            "file_name": match.group(2) or None,
            "url_type": "board",
        }

    # Make URL
    match = _MAKE_RE.match(parsed.path)
    if match:
        return {
            "file_key": match.group(1),
            "node_id": node_id,
            "file_name": match.group(2) or None,
            "url_type": "make",
        }

    # Standard design/file URL
    match = _DESIGN_RE.match(parsed.path)
    if match:
        return {
            "file_key": match.group(1),
            "node_id": node_id,
            "file_name": match.group(2) or None,
            "url_type": "design",
        }

    raise ValueError(f"Invalid Figma URL path: {parsed.path}")


def validate_figma_url(url: str) -> bool:
    """Check if a URL is a valid Figma design/file URL."""
    if not url:
        return False
    try:
        parse_figma_url(url)
        return True
    except ValueError:
        return False


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # Support both `url_parser.py <url>` and `url_parser.py parse <url>`
    target = sys.argv[-1]
    try:
        result = parse_figma_url(target)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
