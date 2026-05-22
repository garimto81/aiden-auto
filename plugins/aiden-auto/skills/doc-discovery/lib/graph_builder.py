"""Layer 1: frontmatter-based reverse-dependency graph builder.

Builds a forward + reverse adjacency graph by parsing YAML frontmatter
in .md files for typed edges (derivative-of, references, supersedes)
and inline markdown links.

Stdlib-only by design. PyYAML is used if available for robust parsing,
otherwise a minimal frontmatter parser handles the common cases used
in this repo's PRD/rule documents.
"""
from __future__ import annotations

import os
import re
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

try:
    import yaml  # type: ignore
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# Edge types tracked in Layer 1 MVP. Order matters for reporting.
EDGE_TYPES = ("derivative-of", "supersedes", "references", "link")

# frontmatter delimiter pattern. Matches the leading `---\n...\n---\n` block.
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# inline markdown link to a .md file. Captures the path.
_MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+\.md)(?:#[^)]*)?\)")

# Default corpus directories scanned when no .claude/discovery.yml exists.
DEFAULT_CORPUS_DIRS = (
    # Catch-all — covers any docs/ subtree (English numbered, Korean categorical, etc.)
    # Exclusion patterns (_generated, node_modules, ...) are applied below.
    "docs",
    # Specific paths kept for back-compat with projects that place docs above root
    "docs/00-prd",
    "docs/01-plan",
    "docs/02-design",
    "docs/04-report",
    "docs/05-analysis",
    "docs/templates",
    ".claude/rules",
    ".claude/skills",
)

DEFAULT_EXCLUDE_GLOBS = (
    "**/node_modules/**",
    "**/_generated/**",
    "**/.git/**",
    "**/__pycache__/**",
)


def parse_frontmatter(text: str) -> Dict:
    """Extract YAML frontmatter from a markdown document. Returns {} when absent."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    raw = match.group(1)
    if HAS_YAML:
        try:
            data = yaml.safe_load(raw)
            return data if isinstance(data, dict) else {}
        except yaml.YAMLError:
            return _fallback_parse(raw)
    return _fallback_parse(raw)


def _fallback_parse(raw: str) -> Dict:
    """Minimal frontmatter parser for environments without PyYAML.

    Supports:
      - key: value
      - key:
          - item1
          - item2
      - key: [item1, item2]
    """
    result: Dict[str, object] = {}
    current_key: Optional[str] = None
    current_list: Optional[List[str]] = None

    for raw_line in raw.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        # list item under a previously-started multi-line key
        list_match = re.match(r"^\s+-\s+(.+)$", line)
        if list_match and current_list is not None:
            current_list.append(list_match.group(1).strip().strip("\"'"))
            continue

        # key: value | key: | key: [a, b]
        kv_match = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if not kv_match:
            continue
        key, value = kv_match.group(1), kv_match.group(2).strip()
        # close the open list when a new top-level key arrives
        if current_list is not None and current_key is not None:
            result[current_key] = current_list
            current_list = None

        if not value:
            current_key = key
            current_list = []
            continue
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1]
            items = [s.strip().strip("\"'") for s in inner.split(",") if s.strip()]
            result[key] = items
        else:
            result[key] = value.strip().strip("\"'")
        current_key = key
        current_list = None

    if current_list is not None and current_key is not None:
        result[current_key] = current_list
    return result


def _normalize_value(value) -> List[str]:
    """Coerce a frontmatter field into a list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _resolve_target(base_file: Path, target: str, root: Path) -> Optional[str]:
    """Resolve a frontmatter or link target to a normalized repo-relative path.

    Resolution order:
      1. Repo-relative match (root / target)
      2. Sibling match (base_file.parent / target)
      3. Filename match anywhere under root (first hit, deterministic by sort)
    """
    # strip URL fragments
    target = target.split("#", 1)[0].strip()
    if not target:
        return None

    candidates: List[Path] = []
    raw = Path(target)
    if not raw.is_absolute():
        candidates.append((root / raw).resolve())
        candidates.append((base_file.parent / raw).resolve())

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            try:
                return str(candidate.relative_to(root)).replace("\\", "/")
            except ValueError:
                return str(candidate).replace("\\", "/")

    # filename-only match (e.g. "Overview.md" referenced from anywhere)
    name = raw.name
    if name == target or "/" not in target:
        try:
            matches = sorted(root.rglob(name))
            for match in matches:
                if match.is_file():
                    return str(match.relative_to(root)).replace("\\", "/")
        except (OSError, PermissionError):
            pass

    # unresolvable but still record as logical node so callers see the gap
    return target.replace("\\", "/")


class DocGraph:
    """Forward + reverse adjacency for typed edges between document nodes."""

    def __init__(self, root: Path):
        self.root = root
        # node -> edge_type -> set(targets)
        self.forward: Dict[str, Dict[str, Set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )
        # node -> edge_type -> set(sources)
        self.reverse: Dict[str, Dict[str, Set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )
        self.nodes: Set[str] = set()
        self.unresolved: Set[Tuple[str, str, str]] = set()

    def add_edge(self, source: str, edge_type: str, target: str) -> None:
        if not source or not target or source == target:
            return
        self.forward[source][edge_type].add(target)
        self.reverse[target][edge_type].add(source)
        self.nodes.add(source)
        self.nodes.add(target)

    def reverse_traversal(
        self,
        target: str,
        edge_types: Optional[Iterable[str]] = None,
        transitive: bool = True,
    ) -> Dict[int, Set[str]]:
        """Return BFS layers of files affected when `target` changes.

        Layer 0 contains the target itself; layer 1 = direct dependents,
        layer 2+ = transitive dependents. Empty when target is a leaf.
        """
        types = tuple(edge_types) if edge_types else EDGE_TYPES
        layers: Dict[int, Set[str]] = {0: {target}}
        seen: Set[str] = {target}
        frontier: deque = deque([(target, 0)])

        while frontier:
            node, depth = frontier.popleft()
            if not transitive and depth >= 1:
                continue
            for edge_type in types:
                sources = self.reverse.get(node, {}).get(edge_type, set())
                for src in sources:
                    if src in seen:
                        continue
                    seen.add(src)
                    layers.setdefault(depth + 1, set()).add(src)
                    frontier.append((src, depth + 1))

        return layers


def _is_excluded(path: Path) -> bool:
    """Check whether a path matches any exclusion glob.

    Walks up the parent chain so that `node_modules/foo/bar.md` is excluded
    by `**/node_modules/**` even when iteration started inside it.
    """
    parts = set(path.parts)
    # Fast-path: any segment matches a known noisy directory
    noise = {"node_modules", "_generated", ".git", "__pycache__",
             "dist", "build", ".next", "_archived"}
    return any(p in parts for p in noise)


def _iter_files(root: Path, include_exts: Tuple[str, ...]) -> Iterable[Path]:
    """Walk the configured corpus directories under `root`. Skips noise dirs
    (node_modules, .git, __pycache__, etc.) per DEFAULT_EXCLUDE_GLOBS."""
    for sub in DEFAULT_CORPUS_DIRS:
        base = root / sub
        if not base.exists() or not base.is_dir():
            continue
        for ext in include_exts:
            try:
                for path in base.rglob(f"*{ext}"):
                    if path.is_file() and not _is_excluded(path):
                        yield path
            except (OSError, PermissionError):
                continue


def _extract_edges(file_path: Path, root: Path) -> List[Tuple[str, str, str]]:
    """Parse a single file and return (source, edge_type, target) tuples."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    src = str(file_path.relative_to(root)).replace("\\", "/")
    edges: List[Tuple[str, str, str]] = []

    fm = parse_frontmatter(text)
    for edge_type in ("derivative-of", "references", "supersedes"):
        targets = _normalize_value(fm.get(edge_type)) if fm else []
        for raw in targets:
            resolved = _resolve_target(file_path, raw, root)
            if resolved:
                edges.append((src, edge_type, resolved))

    # body markdown links — weak signal, only md targets
    body_start = 0
    fm_match = _FRONTMATTER_RE.match(text)
    if fm_match:
        body_start = fm_match.end()
    body = text[body_start:]
    for match in _MD_LINK_RE.finditer(body):
        target_raw = match.group(1)
        if target_raw.startswith(("http://", "https://", "mailto:")):
            continue
        resolved = _resolve_target(file_path, target_raw, root)
        if resolved:
            edges.append((src, "link", resolved))

    return edges


def build_graph(root: Path, include_exts: Tuple[str, ...] = (".md",)) -> DocGraph:
    """Scan the project and build the typed reverse-adjacency graph."""
    graph = DocGraph(root=root)
    for path in _iter_files(root, include_exts):
        for src, edge_type, target in _extract_edges(path, root):
            graph.add_edge(src, edge_type, target)
        rel = str(path.relative_to(root)).replace("\\", "/")
        graph.nodes.add(rel)
    return graph


def impact_analysis(
    graph: DocGraph,
    target: str,
    transitive: bool = True,
    edge_types: Optional[Iterable[str]] = None,
) -> Dict:
    """High-level wrapper used by CLI and downstream agents."""
    layers = graph.reverse_traversal(target, edge_types=edge_types, transitive=transitive)
    direct = sorted(layers.get(1, set()))
    transitive_files: Dict[int, List[str]] = {
        depth: sorted(files) for depth, files in layers.items() if depth >= 2
    }
    total = sum(len(v) for v in layers.values()) - 1  # exclude target itself

    return {
        "target": target,
        "exists": target in graph.nodes,
        "direct": direct,
        "transitive": transitive_files,
        "total_affected": max(total, 0),
    }


def to_json(report: Dict) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False)


def to_text(report: Dict) -> str:
    lines: List[str] = []
    target = report["target"]
    total = report["total_affected"]
    if total == 0:
        lines.append(f"OK  {target} — 영향 받는 파일 없음")
        return "\n".join(lines)

    lines.append(f"IMPACT  {target} → {total} files affected")
    if report["direct"]:
        lines.append(f"  Direct ({len(report['direct'])}):")
        for path in report["direct"]:
            lines.append(f"    - {path}")
    for depth, files in sorted(report["transitive"].items()):
        if not files:
            continue
        lines.append(f"  Transitive depth={depth} ({len(files)}):")
        for path in files:
            lines.append(f"    - {path}")
    if not report["exists"]:
        lines.append("  WARN  target not found in scanned corpora — graph may be incomplete")
    return "\n".join(lines)
