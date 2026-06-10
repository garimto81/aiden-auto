#!/usr/bin/env python3
"""threeway - 3-way merge helper for bidirectional Confluence sync.

Wraps `git merge-file` so the bidirectional sync orchestrator can merge a
document edited on BOTH sides (local Markdown + Confluence) against the
last-synced common ancestor (base).

Design contract (plan 2026-06-10, decision 2 — "3-way 자동 병합"):
    - Non-overlapping changes auto-merge.
    - Only overlapping line edits produce conflict markers → caller stops.
    - Body only: the caller strips frontmatter before calling (frontmatter is
      ours-fixed, never merged).

`git merge-file` arg order is <CURRENT> <BASE> <OTHER>:
    CURRENT = ours   (current local MD)
    BASE    = base   (last-synced common ancestor)
    OTHER   = theirs (Confluence page converted back to MD)
`-p` prints the merged result to stdout and leaves all inputs untouched
(read-only merge — essential since we may decide NOT to write on conflict).

Exit code: 0 = clean, 1..127 = number of conflict hunks, >=128 = fatal.
"""

import hashlib
import re
import subprocess
import tempfile
from pathlib import Path

# Merge outcome statuses
CLEAN = "CLEAN"
CONFLICT = "CONFLICT"


def sha256_text(text):
    """Stable sha256 hex of a unicode string (utf-8, prefixed 'sha256:')."""
    return "sha256:" + hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def normalize_for_compare(text):
    """Normalize MD body for drift comparison (cosmetic-change tolerant).

    Confluence re-formats stored XHTML on save (whitespace/attribute reorder),
    which round-trips back as cosmetically different MD even when the meaning is
    identical. Comparing normalized forms avoids these false 'remote changed'
    signals (plan risk: cosmetic 거짓 drift).

    Strips: HTML comments, trailing whitespace, blank-line runs, leading/
    trailing whitespace. Preserves line structure otherwise so genuine edits
    still differ.
    """
    if not text:
        return ""
    # Drop HTML comments (e.g. <!-- confluence-macro: ... --> round-trip noise)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # Normalize line endings, strip trailing ws per line
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    # Collapse 2+ blank lines into one
    out = []
    blank = False
    for ln in lines:
        if ln == "":
            if not blank:
                out.append(ln)
            blank = True
        else:
            out.append(ln)
            blank = False
    return "\n".join(out).strip()


def has_conflict_markers(text):
    """True if text contains git conflict markers (unresolved merge)."""
    return bool(re.search(r"^<{7} ", text, re.MULTILINE)) and \
        bool(re.search(r"^>{7} ", text, re.MULTILINE))


def merge_files(ours_path, base_path, theirs_path,
                labels=("ours (local)", "base (last sync)", "theirs (confluence)")):
    """Run `git merge-file -p` on three files. Returns (status, merged_text).

    status is CLEAN (rc 0) or CONFLICT (rc 1..127). Raises RuntimeError on
    fatal git error (rc >= 128).
    """
    cmd = [
        "git", "merge-file", "-p",
        "-L", labels[0], "-L", labels[1], "-L", labels[2],
        str(ours_path), str(base_path), str(theirs_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    rc = proc.returncode
    if rc == 0:
        return (CLEAN, proc.stdout)
    if 1 <= rc < 128:
        return (CONFLICT, proc.stdout)
    raise RuntimeError(f"git merge-file fatal (rc={rc}): {proc.stderr.strip()}")


def merge_texts(ours, base, theirs,
                labels=("ours (local)", "base (last sync)", "theirs (confluence)")):
    """3-way merge three in-memory strings. Returns (status, merged_text).

    Writes the three inputs to a scratch dir, delegates to merge_files, and
    cleans up. Trailing newline is normalized so single-line docs merge.
    """
    def _nl(s):
        s = s if s is not None else ""
        return s if s.endswith("\n") else s + "\n"

    tmp = Path(tempfile.mkdtemp(prefix="threeway_"))
    try:
        op = tmp / "ours"
        bp = tmp / "base"
        tp = tmp / "theirs"
        op.write_text(_nl(ours), encoding="utf-8")
        bp.write_text(_nl(base), encoding="utf-8")
        tp.write_text(_nl(theirs), encoding="utf-8")
        return merge_files(op, bp, tp, labels=labels)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
