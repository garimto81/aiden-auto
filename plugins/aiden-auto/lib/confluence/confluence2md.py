#!/usr/bin/env python3
"""confluence2md - reverse converter (Confluence storage format -> Markdown).

The pull half of bidirectional sync. Mirrors md2confluence.py's forward
pipeline in reverse:

    storage XHTML
      -> [macro classify: convert | preserve-verbatim]
      -> vanilla HTML (+ confluence-storage placeholders)
      -> pandoc -f html -t gfm
      -> restore placeholders as ```confluence-storage fences
      -> strip causality panel

Macro 3-classification (plan 2026-06-10):
    convert         : code / info,note,warning,tip / expand / image / link / layout
    preserve-verbatim: toc, status, children, anchor, excerpt-include, jira, ...
                       AND any unknown macro (allowlist-of-convertibles → the
                       rest is preserved, so future macros never silently drop).

Lossless contract: a preserved macro becomes
    ```confluence-storage name=<macro>
    <original storage xml verbatim>
    ```
which md2confluence.py re-injects verbatim on the next push, so proprietary
features (e.g. the Confluence Table of Contents macro) survive the round-trip.

Network-free: callers pass the storage string (fetched elsewhere). pandoc is
the only external dependency, reused exactly like md2confluence.md_to_html.
"""

import re
import subprocess
import sys
from html import escape as html_escape, unescape as html_unescape

# Macros that have a faithful Markdown / vanilla-HTML representation.
# Everything else is preserved verbatim (lossless).
CONVERTIBLE_MACROS = {"code", "info", "note", "warning", "tip", "expand"}

# Fenced block language tag for preserved storage (round-trip contract with
# md2confluence._restore_preserved_storage).
PRESERVE_FENCE = "confluence-storage"

_PLACEHOLDER = "CONFLUENCESTOREBLOCK{n}X"
_PLACEHOLDER_RE = re.compile(r"CONFLUENCESTOREBLOCK(\d+)X")

# Signature that identifies the auto-generated causality Info panel emitted by
# md2confluence.build_causality_panel — stripped on pull so it is never folded
# back into the body (would otherwise duplicate-grow each round-trip).
_CAUSALITY_SIG = "문서 인과관계"


# ---------------------------------------------------------------------------
# Balanced structured-macro scanner
# ---------------------------------------------------------------------------

_MACRO_TOKEN = re.compile(r"<ac:structured-macro\b[^>]*?>|</ac:structured-macro>")


def _macro_name(open_or_full):
    m = re.search(r'ac:name="([^"]+)"', open_or_full)
    return m.group(1) if m else ""


def _top_level_macros(s):
    """Yield (start, end, text) for each top-level <ac:structured-macro>.

    Respects nesting (expand/info bodies may contain nested macros) and
    self-closing macros (`<ac:structured-macro .../>`).
    """
    spans = []
    depth = 0
    open_start = None
    for tok in _MACRO_TOKEN.finditer(s):
        text = tok.group(0)
        if text.startswith("</"):
            if depth > 0:
                depth -= 1
                if depth == 0 and open_start is not None:
                    spans.append((open_start, tok.end(), s[open_start:tok.end()]))
                    open_start = None
        else:
            self_closing = text.rstrip().endswith("/>")
            if self_closing:
                if depth == 0:
                    spans.append((tok.start(), tok.end(), text))
            else:
                if depth == 0:
                    open_start = tok.start()
                depth += 1
    return spans


# ---------------------------------------------------------------------------
# Convertible macro -> vanilla HTML
# ---------------------------------------------------------------------------

def _param(macro_text, name):
    m = re.search(
        rf'<ac:parameter\s+ac:name="{re.escape(name)}"[^>]*>(.*?)</ac:parameter>',
        macro_text, re.DOTALL,
    )
    return m.group(1).strip() if m else ""


def _rich_body(macro_text):
    m = re.search(r"<ac:rich-text-body>(.*?)</ac:rich-text-body>", macro_text, re.DOTALL)
    return m.group(1) if m else ""


def _plain_body(macro_text):
    m = re.search(r"<ac:plain-text-body>(.*?)</ac:plain-text-body>", macro_text, re.DOTALL)
    if not m:
        return ""
    body = m.group(1).strip()
    # Strip the OUTER CDATA wrapper only (a non-greedy CDATA regex would stop at
    # the first ]]> and break md2confluence's split-CDATA escape), then reverse
    # the escape: `]]]]><![CDATA[>` -> `]]>`.
    if body.startswith("<![CDATA[") and body.endswith("]]>"):
        body = body[len("<![CDATA["):-len("]]>")]
    return body.replace("]]]]><![CDATA[>", "]]>")


def _convert_code(macro_text):
    lang = _param(macro_text, "language") or "text"
    code = _plain_body(macro_text)
    return f'<pre><code class="{html_escape(lang)}">{html_escape(code)}</code></pre>'


def _convert_panel(macro_text, name, transform_inner):
    body = _rich_body(macro_text)
    if _CAUSALITY_SIG in body:
        return ""  # auto-generated causality panel — drop (regenerated on push)
    inner = transform_inner(body)
    label = {"info": "ℹ️", "note": "📝", "tip": "💡", "warning": "⚠️"}.get(name, "")
    prefix = f"<p><strong>{label}</strong></p>" if label else ""
    return f"<blockquote>{prefix}{inner}</blockquote>"


def _convert_expand(macro_text, transform_inner):
    title = _param(macro_text, "title") or "펼쳐 보기"
    body = transform_inner(_rich_body(macro_text))
    # Blank lines around body so pandoc parses inner block content / fences,
    # matching md2confluence's <details> authoring contract.
    return f"<details><summary>{title}</summary>\n\n{body}\n\n</details>"


# ---------------------------------------------------------------------------
# Non-macro Confluence constructs (image / link / layout)
# ---------------------------------------------------------------------------

def _convert_images(html):
    """ac:image (attachment or external url) -> <img>. Returns (html, filenames)."""
    filenames = []

    def _repl(m):
        block = m.group(0)
        alt_m = re.search(r'ac:alt="([^"]*)"', block)
        alt = alt_m.group(1) if alt_m else ""
        att = re.search(r'<ri:attachment\s+ri:filename="([^"]+)"', block)
        if att:
            filenames.append(att.group(1))
            return f'<img src="{html_escape(att.group(1))}" alt="{html_escape(alt)}">'
        url = re.search(r'<ri:url\s+ri:value="([^"]+)"', block)
        if url:
            return f'<img src="{html_escape(url.group(1))}" alt="{html_escape(alt)}">'
        return ""

    html = re.sub(r"<ac:image\b.*?</ac:image>", _repl, html, flags=re.DOTALL)
    return html, filenames


def _convert_links(html, link_resolver):
    """ac:link to a Confluence page -> <a href="relpath.md">.

    link_resolver maps page title -> repo-relative .md path. Unresolved links
    degrade to plain text (best-effort, accepted fidelity loss).
    """
    def _repl(m):
        block = m.group(0)
        title_m = re.search(r'ri:content-title="([^"]+)"', block)
        body_m = re.search(r"<ac:plain-text-link-body><!\[CDATA\[(.*?)\]\]>", block, re.DOTALL)
        if not body_m:
            body_m = re.search(r"<ac:link-body>(.*?)</ac:link-body>", block, re.DOTALL)
        text = (body_m.group(1) if body_m else (title_m.group(1) if title_m else "")).strip()
        title = title_m.group(1) if title_m else ""
        rel = link_resolver.get(title) if link_resolver else None
        if rel:
            return f'<a href="{html_escape(rel)}">{html_escape(text)}</a>'
        return html_escape(text)

    return re.sub(r"<ac:link\b.*?</ac:link>", _repl, html, flags=re.DOTALL)


def _unwrap_layout(html):
    """Strip ac:layout / layout-section / layout-cell wrappers (content kept)."""
    html = re.sub(r"</?ac:layout(?:-section|-cell)?\b[^>]*>", "", html)
    return html


# ---------------------------------------------------------------------------
# Recursive macro transform
# ---------------------------------------------------------------------------

def _transform(storage, preserved, ledger):
    """Recursively convert convertible macros; extract preserved ones to tokens.

    preserved: list mutated with original storage XML for each preserved macro.
    ledger: {"converted": [...], "preserved": [...], "dropped": [...]}.
    """
    spans = _top_level_macros(storage)
    if not spans:
        return storage

    out = []
    cursor = 0

    def _inner(s):
        return _transform(s, preserved, ledger)

    for start, end, text in spans:
        out.append(storage[cursor:start])
        cursor = end
        name = _macro_name(text)
        if name == "code":
            ledger["converted"].append(name)
            out.append(_convert_code(text))
        elif name in ("info", "note", "warning", "tip"):
            converted = _convert_panel(text, name, _inner)
            ledger["converted"].append(name)
            out.append(converted)
        elif name == "expand":
            ledger["converted"].append(name)
            out.append(_convert_expand(text, _inner))
        else:
            # preserve verbatim (toc/status/children/... or unknown)
            idx = len(preserved)
            preserved.append((name or "unknown", text))
            ledger["preserved"].append(name or "unknown")
            out.append(f"<p>{_PLACEHOLDER.format(n=idx)}</p>")

    out.append(storage[cursor:])
    return "".join(out)


# ---------------------------------------------------------------------------
# pandoc html -> gfm  (mirror of md2confluence.md_to_html)
# ---------------------------------------------------------------------------

def _pandoc_html_to_md(html):
    is_win = sys.platform == "win32"
    base_cmd = [
        "pandoc",
        "-f", "html",
        "-t", "gfm-raw_html",
        "--wrap=none",
    ]
    cmd = ["cmd", "/c"] + base_cmd if is_win else base_cmd
    result = subprocess.run(
        cmd, input=html, capture_output=True,
        text=True, encoding="utf-8", timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Pandoc (html->gfm) failed: {result.stderr}")
    return result.stdout


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def confluence_to_md(storage, page_title=None, link_resolver=None, run_pandoc=True):
    """Convert Confluence storage format to Markdown.

    Returns (markdown, ledger). ledger = {converted, preserved, dropped,
    attachments}. `dropped` is always [] by design (unknown macros are
    preserved, not dropped); a non-empty `dropped` signals the caller to warn
    and hold the sync (silent-loss guard).

    link_resolver: optional {page_title: repo_rel_path} for reverse cross-links.
    run_pandoc=False returns the pre-pandoc vanilla HTML (for unit testing the
    classification/preservation stages without a pandoc dependency).
    """
    ledger = {"converted": [], "preserved": [], "dropped": [], "attachments": []}
    preserved = []
    link_resolver = link_resolver or {}

    # 1) Recursive macro transform (convert known, tokenize preserved)
    html = _transform(storage or "", preserved, ledger)

    # 2) Non-macro constructs
    html, filenames = _convert_images(html)
    ledger["attachments"] = filenames
    html = _convert_links(html, link_resolver)
    html = _unwrap_layout(html)

    if not run_pandoc:
        md = html
    else:
        # 3) pandoc html -> gfm
        md = _pandoc_html_to_md(html)

    # 4) Restore preserved macros as ```confluence-storage fences
    def _restore(m):
        idx = int(m.group(1))
        name, xml = preserved[idx]
        return f"```{PRESERVE_FENCE} name={name}\n{xml}\n```"

    md = _PLACEHOLDER_RE.sub(_restore, md)

    return md, ledger
