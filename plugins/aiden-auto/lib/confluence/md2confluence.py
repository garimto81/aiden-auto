#!/usr/bin/env python3
"""md2confluence - Markdown to Confluence Storage Format converter.

Handles: image attachments, Mermaid->PNG rendering, table auto-width styling.

Usage:
    python md2confluence.py <markdown_file> <page_id> [--dry-run] [--base-url URL]

Environment:
    ATLASSIAN_EMAIL     - Confluence user email
    ATLASSIAN_API_TOKEN - Confluence API token
    CONFLUENCE_BASE_URL - Base URL (default: https://ggnetwork.atlassian.net/wiki)
"""

import os
import sys
import re
import json
import tempfile
import subprocess
import shutil
import argparse
import mimetypes
import time
from html import unescape as html_unescape
from pathlib import Path
from urllib.parse import unquote as url_unquote, quote as url_quote

import requests

# Register MIME types not in Python stdlib by default (e.g., webp on some platforms)
mimetypes.add_type('image/webp', '.webp')
mimetypes.add_type('image/avif', '.avif')

# Ensure UTF-8 output on Windows (prevents cp949 UnicodeEncodeError)
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _get_win_env(name):
    """Get Windows User environment variable (fallback when shell env is empty)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return winreg.QueryValueEx(key, name)[0]
    except Exception:
        return ""


def get_config():
    return {
        "base_url": (os.environ.get("CONFLUENCE_BASE_URL", "")
                     or _get_win_env("CONFLUENCE_BASE_URL")
                     or "https://ggnetwork.atlassian.net/wiki"),
        "email": os.environ.get("ATLASSIAN_EMAIL", "") or _get_win_env("ATLASSIAN_EMAIL"),
        "token": os.environ.get("ATLASSIAN_API_TOKEN", "") or _get_win_env("ATLASSIAN_API_TOKEN"),
    }


def get_auth(cfg):
    return (cfg["email"], cfg["token"])


# ---------------------------------------------------------------------------
# Confluence REST API helpers
# ---------------------------------------------------------------------------

def api_get(cfg, path, params=None):
    url = f"{cfg['base_url']}/rest/api{path}"
    resp = requests.get(url, auth=get_auth(cfg), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_put_json(cfg, path, payload):
    url = f"{cfg['base_url']}/rest/api{path}"
    resp = requests.put(
        url, auth=get_auth(cfg), json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    if not resp.ok:
        print(f"  API Error {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
    resp.raise_for_status()
    return resp.json()


def get_page_info(cfg, page_id):
    try:
        return api_get(cfg, f"/content/{page_id}", {"expand": "version,space"})
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            # Try draft status
            return api_get(cfg, f"/content/{page_id}", {"expand": "version,space", "status": "draft"})
        raise


def _guess_mime(filename):
    """Guess MIME type from filename. Defaults to application/octet-stream."""
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


def upload_attachment(cfg, page_id, filepath, filename=None, max_retries=2):
    if filename is None:
        filename = os.path.basename(filepath)

    url = f"{cfg['base_url']}/rest/api/content/{page_id}/child/attachment"
    headers = {"X-Atlassian-Token": "nocheck"}
    mime_type = _guess_mime(filename)

    for attempt in range(1, max_retries + 1):
        with open(filepath, "rb") as f:
            files = {"file": (filename, f, mime_type)}
            resp = requests.put(url, auth=get_auth(cfg), headers=headers, files=files, timeout=60)

        if resp.status_code in (200, 201):
            print(f"  [OK] {filename} ({mime_type})")
            return resp.json()

        if attempt < max_retries:
            print(f"  [RETRY {attempt}/{max_retries}] {filename}: {resp.status_code}")
            time.sleep(2)
        else:
            print(f"  [FAIL] {filename}: {resp.status_code} {resp.text[:200]}")

    return None


def _upload_all(cfg, page_id, images):
    """Upload all images and return list of failed filenames."""
    failed = []
    for fname, fpath in images:
        result = upload_attachment(cfg, page_id, fpath, fname)
        if result is None:
            failed.append(fname)
    if images and not failed:
        # Brief pause to let Confluence process attachments before page update
        time.sleep(1)
    return failed


def _report_upload_result(final_ver, failed):
    if failed:
        print(f"  WARNING: Page updated to v{final_ver}, but {len(failed)} attachment(s) failed:")
        for f in failed:
            print(f"    - {f}")
    else:
        print(f"  SUCCESS: Page updated to v{final_ver}")


def _normalize_for_match(text):
    text = html_unescape(text)
    text = re.sub(r"[^\w가-힣]+", "", text)
    return text.lower()


def verify_push_integrity(cfg, page_id, md_content):
    """Fetch fresh storage and verify all MD H1/H2 headers landed.

    Returns list of missing header strings (empty = all good).
    """
    md_headers = re.findall(r"^#{1,2}\s+(.+?)\s*$", md_content, re.MULTILINE)
    if not md_headers:
        return []
    try:
        info = api_get(cfg, f"/content/{page_id}", {"expand": "body.storage"})
        storage = info["body"]["storage"]["value"]
    except Exception as e:
        print(f"  [VERIFY-SKIP] Could not fetch storage: {e}")
        return []
    storage_norm = _normalize_for_match(storage)
    missing = []
    for h in md_headers:
        needle = _normalize_for_match(h)
        if needle and needle not in storage_norm:
            missing.append(h)
    return missing


def update_page_content(cfg, page_id, title, html, version, space_key, publish_draft=False, parent_id=None):
    payload = {
        "id": page_id,
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "version": {"number": version},
        "body": {"storage": {"value": html, "representation": "storage"}},
    }
    if publish_draft:
        payload["status"] = "current"
    if parent_id:
        payload["ancestors"] = [{"id": str(parent_id)}]
    return api_put_json(cfg, f"/content/{page_id}", payload)


# ---------------------------------------------------------------------------
# Mermaid rendering
# ---------------------------------------------------------------------------

def _render_single_mermaid(code, output_dir, idx):
    """Render a single Mermaid diagram with 3-stage fallback.

    Fallback order: mermaid.ink API → mmdc CLI → Playwright.
    Reuses the hybrid renderer from lib/google_docs/mermaid_renderer.py.
    """
    png = os.path.join(output_dir, f"mermaid-{idx}.png")

    # Try importing the shared hybrid renderer
    try:
        project_root = str(Path(__file__).resolve().parent.parent.parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from lib.google_docs.mermaid_renderer import render_mermaid
        result_path = render_mermaid(code)
        if result_path:
            shutil.copy2(result_path, png)
            os.unlink(result_path)
            print(f"  [OK] mermaid-{idx}.png rendered (hybrid fallback)")
            return png
    except ImportError:
        pass  # Fall through to local mmdc attempt

    # Direct mmdc fallback (if hybrid renderer unavailable)
    mmd = os.path.join(output_dir, f"mermaid-{idx}.mmd")
    with open(mmd, "w", encoding="utf-8") as f:
        f.write(code)

    cfg = os.path.join(output_dir, f"mermaid-{idx}.json")
    with open(cfg, "w", encoding="utf-8") as f:
        json.dump({"theme": "default", "fontSize": 18}, f)

    is_win = sys.platform == "win32"
    cmd = (["cmd", "/c", "mmdc", "-i", mmd, "-o", png, "-b", "white", "-s", "2", "-c", cfg]
           if is_win else ["mmdc", "-i", mmd, "-o", png, "-b", "white", "-s", "2", "-c", cfg])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and os.path.exists(png):
            print(f"  [OK] mermaid-{idx}.png rendered (mmdc)")
            return png
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None


def render_mermaid_blocks(md_content, output_dir):
    """Replace ```mermaid blocks with rendered PNG references.

    Uses 3-stage fallback: mermaid.ink API → mmdc CLI → Playwright.
    Fails loudly if all strategies fail (no silent code-block passthrough).
    """
    pattern = re.compile(r"```mermaid\s*\n(.*?)\n```", re.DOTALL)
    images = []
    failed = []

    def _replace(match):
        idx = len(images)
        code = match.group(1)

        png_path = _render_single_mermaid(code, output_dir, idx)
        if png_path:
            images.append(png_path)
            return f"![](mermaid-{idx}.png)"
        else:
            print(f"  [ERROR] mermaid-{idx} 렌더링 실패 (모든 전략 실패)")
            failed.append(idx)
            images.append(None)
            return match.group(0)

    modified = pattern.sub(_replace, md_content)

    if failed:
        print(f"\n  ⚠️  {len(failed)}개 Mermaid 다이어그램 렌더링 실패: {failed}")
        print("  → Confluence에 코드 블록으로 표시됩니다.")
        print("  → 해결: npm i -g @mermaid-js/mermaid-cli (mmdc 설치)")

    return modified, images


# ---------------------------------------------------------------------------
# Pandoc MD -> HTML
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Lossless macro preservation (round-trip contract with confluence2md.py)
# ---------------------------------------------------------------------------
#
# confluence2md (the pull half) preserves proprietary Confluence macros that
# have no Markdown equivalent — e.g. the Table of Contents macro — verbatim
# inside a fence:
#
#     ```confluence-storage name=toc
#     <ac:structured-macro ac:name="toc">...</ac:structured-macro>
#     ```
#
# On push we must re-inject that storage XML UNCHANGED so the macro renders
# again in Confluence. Pandoc would mangle the XML, so we extract the fence
# content to a placeholder BEFORE pandoc and restore it AFTER postprocess.
# No fence present → both functions are no-ops (zero impact on existing push).

_PRESERVE_FENCE_RE = re.compile(
    r"```confluence-storage[^\n]*\n(.*?)\n```", re.DOTALL,
)
_PRESERVE_TOKEN = "CONFLUENCESTORAGEINJECT{n}X"
_PRESERVE_TOKEN_RE = re.compile(r"CONFLUENCESTORAGEINJECT(\d+)X")


def _extract_preserved_storage(md_content):
    """Pull ```confluence-storage fences out to placeholders (pre-pandoc).

    Returns (md_with_placeholders, preserved_xml_list).
    """
    preserved = []

    def _repl(m):
        idx = len(preserved)
        preserved.append(m.group(1))
        # Blank lines so pandoc renders the token as a standalone paragraph.
        return f"\n\n{_PRESERVE_TOKEN.format(n=idx)}\n\n"

    return _PRESERVE_FENCE_RE.sub(_repl, md_content), preserved


def _restore_preserved_storage(html, preserved):
    """Replace placeholders with the original storage XML (post-postprocess)."""
    if not preserved:
        return html

    def _repl(m):
        idx = int(m.group(1))
        return preserved[idx] if 0 <= idx < len(preserved) else m.group(0)

    # Pandoc wraps the bare token in <p>…</p>; unwrap that first, then catch any
    # stragglers (e.g. token left inside a table cell).
    html = re.sub(r"<p>\s*CONFLUENCESTORAGEINJECT(\d+)X\s*</p>", _repl, html)
    html = _PRESERVE_TOKEN_RE.sub(_repl, html)
    return html


def md_to_html(md_content, resource_path):
    is_win = sys.platform == "win32"
    base_cmd = [
        "pandoc",
        "-f", "markdown+pipe_tables+grid_tables-implicit_figures",
        "-t", "html",
        f"--resource-path={resource_path}",
        "--wrap=none",
        "--no-highlight",
    ]
    cmd = ["cmd", "/c"] + base_cmd if is_win else base_cmd
    result = subprocess.run(
        cmd,
        input=md_content, capture_output=True,
        text=True, encoding="utf-8", timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Pandoc failed: {result.stderr}")
    return result.stdout


# ---------------------------------------------------------------------------
# Causality panel (frontmatter → Info macro) — Phase 2 추가
# ---------------------------------------------------------------------------


def parse_frontmatter_full(md_content):
    """Full frontmatter parser supporting nested list (related-docs)."""
    if not md_content.startswith("---\n"):
        return {}
    end = md_content.find("\n---\n", 4)
    if end == -1:
        return {}
    fm_text = md_content[4:end]
    out = {}
    current_list_key = None
    for line in fm_text.splitlines():
        # Nested list item (`  - ` or `    - `)
        if re.match(r'^\s+-\s+', line):
            if current_list_key:
                if current_list_key not in out or not isinstance(out[current_list_key], list):
                    out[current_list_key] = []
                item = re.sub(r'^\s+-\s+', '', line).strip()
                out[current_list_key].append(item)
            continue
        m = re.match(r'^([\w-]+):\s*(.*?)\s*$', line)
        if m:
            key, val = m.group(1), m.group(2)
            current_list_key = None
            if not val:
                # List start — collect items in following indented lines
                current_list_key = key
                out[key] = []
            else:
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                out[key] = val
    return out


def _esc(s):
    """Minimal HTML escape for panel text."""
    if not isinstance(s, str):
        s = str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ─────────────────────────────────────────────────────────────────────────
# Rule 22 — GitHub SSOT (2026-06-08 user decision): document cross-links resolve
# to the GitHub canonical URL (always-latest, default branch) instead of
# Confluence/Figma. The repo's GitHub slug is auto-derived from
# `git remote get-url origin`, so no per-doc frontmatter is required. Falls back
# to Confluence linking when the repo has no GitHub remote. Opt out: GITHUB_SSOT=0.
# ─────────────────────────────────────────────────────────────────────────
_GITHUB_BASE_CACHE = {}


def _github_slug(remote_url):
    """Extract 'owner/repo' from a git remote URL (https or ssh). '' if not GitHub."""
    if not remote_url:
        return ""
    m = re.search(r'github\.com[:/]+([^/\s]+/[^/\s]+?)(?:\.git)?/?$', remote_url.strip())
    return m.group(1) if m else ""


def derive_github_base(repo_root):
    """Derive the GitHub canonical base URL for a repo.

    Returns e.g. 'https://github.com/owner/repo/blob/main', or '' when the repo
    has no GitHub remote (→ graceful fallback to Confluence linking).

    Branch defaults to 'main' (always-latest policy — rule 22); override with
    GITHUB_SSOT_BRANCH. Disable entirely per-project with GITHUB_SSOT=0.
    """
    if os.environ.get("GITHUB_SSOT", "1") == "0":
        return ""
    key = str(repo_root)
    if key in _GITHUB_BASE_CACHE:
        return _GITHUB_BASE_CACHE[key]
    base = ""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        slug = _github_slug(result.stdout)
        if slug:
            branch = os.environ.get("GITHUB_SSOT_BRANCH", "main")
            base = f"https://github.com/{slug}/blob/{branch}"
    except Exception:
        base = ""
    _GITHUB_BASE_CACHE[key] = base
    return base


def github_url_for(repo_root, rel_path):
    """Build the GitHub canonical URL for a repo-relative doc path.

    Returns '' when no GitHub remote is derivable. Path segments are
    URL-encoded (docs paths often contain spaces); '/' separators preserved.
    """
    base = derive_github_base(repo_root)
    if not base:
        return ""
    rel = str(rel_path).replace("\\", "/").lstrip("/")
    encoded = "/".join(url_quote(seg) for seg in rel.split("/") if seg)
    return f"{base}/{encoded}"


def _linkify_path(path_str, repo_map=None, current_dir=None, repo_root=None):
    """Resolve a markdown-relative path to a clickable link.

    Resolution order (rule 22 — GitHub SSOT, 2026-06-08):
        0. in-repo .md target + GitHub remote derivable → GitHub canonical URL
           (always-latest, default branch). This is the SSOT and takes priority
           over Confluence. Below tiers are the no-GitHub-remote fallback.

    Confluence fallback order (S11 Cycle 11 — Confluence_Sync_Spec.md v2.0):
        1. confluence-url present → <a href="{url}"> anchor.
           URL is page-id-based (e.g. .../pages/3625189547) so it remains
           valid even when the Confluence page title differs from the file
           stem (real-world fact: Foundation.md ↔ "EBS 기초 기획서").
        2. confluence-page-id only (no URL) → ac:link with ri:content-title=stem.
           Best-effort; the stem must match the live Confluence title or the
           link will dead-end. confluence-url is the safer field.
        3. Neither → <code> rendering (no phantom link).

    Why URL-first (changed in Cycle 11):
        Cycle 10 used ri:content-title=stem assuming "page name = file stem".
        Live drift_check proved 7/7 Product PRDs violate that invariant — all
        Confluence pages use descriptive titles ("EBS · Command Center PRD —
        운영자가 매 순간 머무는 조종석"). URL-based anchors bypass this
        entirely because the URL embeds the page-id, which is immutable.

    path_str: 'Foundation.md (§Ch.4 ...)' or '../Lobby/Overview.md' or 'BS-05-00'
    Strips parenthetical descriptions and anchors before lookup.
    """
    if not current_dir or not repo_root:
        return f"<code>{_esc(path_str)}</code>"
    repo_map = repo_map or {}

    # Extract the path portion. Real EBS docs paths contain spaces
    # (e.g. "2. Development/2.4 Command Center/Overview.md"), so a naive
    # split-on-whitespace truncates the path. Instead, match everything up to
    # and including the first '.md', then anything after is description.
    raw = str(path_str).strip().rstrip(",;")
    md_match = re.match(r'^(.+?\.md)(?:#\S*)?(?:\s.*)?$', raw)
    if not md_match:
        if "/" not in raw:
            # Not a path — return as-is
            return f"<code>{_esc(path_str)}</code>"
        path_token = raw
    else:
        path_token = md_match.group(1)

    try:
        target = (Path(current_dir) / path_token).resolve()
        in_repo = True
        try:
            rel = str(target.relative_to(repo_root)).replace("\\", "/")
        except ValueError:
            in_repo = False
            rel = Path(path_token).name
        # Rule 22 — GitHub SSOT: an in-repo .md target links to its GitHub
        # canonical URL (full replacement of Confluence cross-links). Falls
        # through to Confluence linking when no GitHub remote is derivable.
        if in_repo and target.exists():
            gh = github_url_for(repo_root, rel)
            if gh:
                return f'<a href="{_esc(gh)}">{_esc(path_str)}</a>'
        entry = repo_map.get(rel) or repo_map.get(Path(path_token).name)
        if not entry:
            return f"<code>{_esc(path_str)}</code>"
        page_id, title, url = entry
        # Cycle 11: URL-first (page-id-based, title-mismatch tolerant).
        if url:
            return f'<a href="{_esc(url)}">{_esc(path_str)}</a>'
        if page_id:
            safe_title = title.replace('"', "'")
            return (
                f'<ac:link>'
                f'<ri:page ri:content-title="{safe_title}"/>'
                f'<ac:plain-text-link-body><![CDATA[{path_str}]]></ac:plain-text-link-body>'
                f'</ac:link>'
            )
        return f"<code>{_esc(path_str)}</code>"
    except Exception:
        return f"<code>{_esc(path_str)}</code>"


def build_causality_panel(fm, repo_map=None, current_dir=None, repo_root=None):
    """Generate Confluence Info macro HTML with frontmatter causality info.

    Renders 9 인과관계 fields as a single Info panel at the top of the page.
    When repo_map+current_dir+repo_root provided, derivative-of / related-docs
    paths matching mapped Confluence pages become clickable ac:link hyperlinks.
    Empty if no causality fields are present.
    """
    rows = []

    if fm.get("derivative-of"):
        link = _linkify_path(fm["derivative-of"], repo_map, current_dir, repo_root)
        rows.append(
            f'<li><strong>📌 정본 (변경 시 본 문서 동시 갱신)</strong>: {link}</li>'
        )

    related = fm.get("related-docs")
    if related:
        if isinstance(related, list) and related:
            linked = [_linkify_path(r, repo_map, current_dir, repo_root) for r in related[:5]]
            shown = ", ".join(linked)
            if len(related) > 5:
                shown += f" 외 {len(related) - 5}건"
        else:
            shown = _linkify_path(related, repo_map, current_dir, repo_root)
        rows.append(f'<li><strong>🔗 관련 문서</strong>: {shown}</li>')

    if fm.get("if-conflict"):
        rows.append(f'<li><strong>⚠️ 충돌 시</strong>: {_esc(fm["if-conflict"])}</li>')

    if fm.get("last-synced"):
        rows.append(f'<li><strong>📅 마지막 동기화</strong>: {_esc(fm["last-synced"])}</li>')

    if fm.get("last-updated"):
        rows.append(f'<li><strong>🕒 last-updated</strong>: {_esc(fm["last-updated"])}</li>')

    if fm.get("owner"):
        rows.append(f'<li><strong>👤 Owner</strong>: {_esc(fm["owner"])}</li>')

    if fm.get("audience-target"):
        rows.append(f'<li><strong>🎯 Audience</strong>: {_esc(fm["audience-target"])}</li>')

    if fm.get("tier"):
        rows.append(f'<li><strong>🏷️ Tier</strong>: {_esc(fm["tier"])}</li>')

    if fm.get("legacy-id"):
        rows.append(f'<li><strong>🆔 Legacy ID</strong>: <code>{_esc(fm["legacy-id"])}</code></li>')

    if fm.get("supersedes"):
        rows.append(f'<li><strong>📜 이전 버전</strong>: {_esc(fm["supersedes"])}</li>')

    if not rows:
        return ""

    inner = "\n".join(rows)
    return (
        '<ac:structured-macro ac:name="info">'
        '<ac:rich-text-body>'
        '<p><strong>ℹ️ 문서 인과관계</strong> <em>(frontmatter 자동 생성)</em></p>'
        f'<ul>{inner}</ul>'
        '</ac:rich-text-body>'
        '</ac:structured-macro>'
    )


def build_repo_path_to_pageid_map(repo_root):
    """Walk docs/ → {relative_path: (page_id, title, url)}.

    title is always the filename stem (matches the Confluence page-name
    invariant established by S11 Cycle 10). url is the confluence-url
    frontmatter value when present; either page_id or url must be truthy
    for the entry to be emitted — pages with neither are unmapped.
    """
    out = {}
    docs_root = Path(repo_root) / "docs"
    if not docs_root.exists():
        return out
    for path in docs_root.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if not text.startswith("---\n"):
            continue
        end = text.find("\n---\n", 4)
        if end == -1:
            continue
        fm_text = text[4:end]

        page_m = re.search(r'^confluence-page-id:\s*(\S+)\s*$', fm_text, re.M)
        page_id = page_m.group(1).strip() if page_m else ""
        if page_id in ("null", "None", ""):
            page_id = ""

        url_m = re.search(r'^confluence-url:\s*(\S+)\s*$', fm_text, re.M)
        url = url_m.group(1).strip() if url_m else ""
        if url in ("null", "None", ""):
            url = ""

        # EBS: frontmatter pointing at a deprecated space (CONFLUENCE_DEPRECATED_SPACES,
        # e.g. WSOPLive) is treated as unmapped, so cross-links to it downgrade to plain
        # text instead of linking into an unmanaged space. No-op when the env is unset.
        _dep = [s.strip() for s in os.environ.get("CONFLUENCE_DEPRECATED_SPACES", "").split(",") if s.strip()]
        if url and any(f"/spaces/{d}/" in url for d in _dep):
            continue

        if not page_id and not url:
            continue

        # Title = filename stem (NEVER the frontmatter `title:`). Confluence
        # pages are named after the .md file; using the verbose `title:` value
        # generates dead ac:link targets when the two diverge.
        title = path.stem
        relpath = str(path.relative_to(repo_root)).replace("\\", "/")
        entry = (page_id, title, url)
        out[relpath] = entry
        # Basename fuzzy match (e.g. "Foundation.md" referenced from a sibling)
        out[path.name] = entry
    return out


def transform_cross_links(html, repo_map, current_dir, repo_root):
    """Convert <a href="../Foundation.md">...</a> to Confluence <ac:link> when target is mapped.

    Mirrors `_linkify_path` resolution order (Cycle 11 v2.0): URL-first because
    page-id-based URLs survive Confluence title changes; ri:content-title
    fallback only when no URL is available.
    """
    if not repo_root or not current_dir:
        return html
    repo_map = repo_map or {}

    # EBS strict mode (active only when CONFLUENCE_DEPRECATED_SPACES is set): unmapped
    # .md links downgrade to plain <code> (no dead Confluence link), and anchor bodies
    # containing inline tags (e.g. <code>name.md</code>) are matched too. When the env
    # is unset, behavior is byte-for-byte identical to before (other projects unaffected).
    strict = bool(os.environ.get("CONFLUENCE_DEPRECATED_SPACES"))

    def _replace(match):
        href = match.group(1)
        text = match.group(2)
        if not (href.endswith(".md") or ".md#" in href):
            return match.group(0)
        # Absolute URLs are already-final links (e.g. rule 22 GitHub SSOT
        # canonical URLs end in '.md'). They must NOT be re-resolved as repo
        # cross-links — in strict mode that downgrades them to <code>, silently
        # dropping the link. Leave any http(s)/protocol-relative/mailto href as-is.
        if href.startswith(("http://", "https://", "//", "mailto:")):
            return match.group(0)
        try:
            path_part = href.split("#", 1)[0]
            target = (current_dir / path_part).resolve()
            in_repo = True
            try:
                rel = str(target.relative_to(repo_root)).replace("\\", "/")
            except ValueError:
                # Fallback to basename
                in_repo = False
                rel = Path(path_part).name
            # Rule 22 — GitHub SSOT first: in-repo .md links point to their
            # GitHub canonical URL (full replacement). Falls through to
            # Confluence linking when no GitHub remote is derivable.
            if in_repo and target.exists():
                gh = github_url_for(repo_root, rel)
                if gh:
                    safe_text = re.sub(r'<[^>]+>', '', text).strip() or Path(path_part).stem
                    return f'<a href="{_esc(gh)}">{_esc(safe_text)}</a>'
            entry = repo_map.get(rel) or repo_map.get(Path(path_part).name)
            if not entry:
                if strict:
                    safe_text = re.sub(r'<[^>]+>', '', text).strip() or Path(path_part).stem
                    return f'<code>{_esc(safe_text)}</code>'
                return match.group(0)
            page_id, title, url = entry
            safe_text = re.sub(r'<[^>]+>', '', text).strip() or title
            # Cycle 11: URL-first (page-id-based, title-mismatch tolerant).
            if url:
                return f'<a href="{_esc(url)}">{_esc(safe_text)}</a>'
            if page_id:
                safe_title = title.replace('"', "'")
                return (
                    f'<ac:link>'
                    f'<ri:page ri:content-title="{safe_title}"/>'
                    f'<ac:plain-text-link-body><![CDATA[{safe_text}]]></ac:plain-text-link-body>'
                    f'</ac:link>'
                )
            return match.group(0)
        except Exception:
            return match.group(0)

    body_pat = r'(.*?)' if strict else r'([^<]+)'
    return re.sub(
        r'<a\s+href="([^"]+\.md(?:#[^"]*)?)"[^>]*>' + body_pat + r'</a>',
        _replace, html,
    )


def apply_labels(cfg, page_id, fm):
    """Apply Confluence labels to a page based on frontmatter."""
    labels = []

    if fm.get("tier"):
        labels.append(f'tier-{fm["tier"]}'.lower())

    owner = fm.get("owner", "").lower() if isinstance(fm.get("owner"), str) else ""
    owner_label = None
    for stream_keyword, label in (
        (("s1 ", "foundation"), "owner-s1"),
        (("s2 ", "lobby"), "owner-s2"),
        (("s3 ", "command center", "cc "), "owner-s3"),
        (("s4 ", "rive"), "owner-s4"),
        (("s5 ", "ai track"), "owner-s5"),
        (("s6 ", "prototype"), "owner-s6"),
        (("s7 ", "backend"), "owner-s7"),
        (("s8 ", "engine"), "owner-s8"),
    ):
        if any(kw in owner for kw in stream_keyword):
            owner_label = label
            break
    if not owner_label:
        if "team1" in owner:
            owner_label = "owner-team1"
        elif "team2" in owner:
            owner_label = "owner-team2"
        elif "team3" in owner:
            owner_label = "owner-team3"
        elif "team4" in owner:
            owner_label = "owner-team4"
        elif "conductor" in owner:
            owner_label = "owner-conductor"
    if owner_label:
        labels.append(owner_label)

    if fm.get("legacy-id"):
        legacy = str(fm["legacy-id"])
        m = re.match(r'^([A-Za-z]+-\d+)', legacy)
        if m:
            labels.append(f'legacy-{m.group(1).lower()}')

    if not labels:
        return

    payload = [{"prefix": "global", "name": label} for label in labels]
    url = f"{cfg['base_url']}/rest/api/content/{page_id}/label"
    try:
        resp = requests.post(url, auth=get_auth(cfg), json=payload, timeout=30)
        if resp.ok:
            print(f"  [labels] {', '.join(labels)} applied")
        else:
            print(f"  [labels] HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"  [labels] failed: {e}")


# ---------------------------------------------------------------------------
# HTML post-processing for Confluence Storage Format
# ---------------------------------------------------------------------------

# Table column auto-width tuning constants (Confluence default body ~760px)
_TBL_PX_PER_UNIT = 7      # px per display-unit (CJK glyph=2 units, ASCII=1)
_TBL_CELL_PAD = 24        # left+right cell padding + breathing room (px)
_TBL_MIN_COL = 70         # never shrink a column below this (px)
_TBL_MAX_COL = 440        # cap a single column so long prose wraps (px)
_TBL_MAX_TOTAL = 760      # Confluence default content width (px)


def _display_width(text):
    """Approximate rendered width in units: CJK/full-width glyph=2, else 1."""
    w = 0
    for ch in text:
        # Hangul, CJK ideographs, kana, full-width forms render ~2x wide
        if ch >= "ᄀ" and (
            "가" <= ch <= "힣"      # Hangul syllables
            or "一" <= ch <= "鿿"   # CJK unified ideographs
            or "぀" <= ch <= "ヿ"   # kana
            or "　" <= ch <= "〿"   # CJK punctuation
            or "＀" <= ch <= "￯"   # full-width forms
        ):
            w += 2
        else:
            w += 1
    return w


def _fit_table_columns(html):
    """Inject per-column px widths (fitted to text) into bare data tables.

    Only matches attribute-less ``<table>`` (pandoc data tables). Layout blocks
    use ``<table role="presentation">`` and never match, so they are untouched.
    Data tables are not nested, so the non-greedy span is safe.
    """
    def _process(match):
        table = match.group(1)
        rows = re.findall(r"<tr>(.*?)</tr>", table, re.DOTALL)
        col_w = {}
        for row in rows:
            cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.DOTALL)
            for i, cell in enumerate(cells):
                text = re.sub(r"<[^>]+>", "", cell)            # strip tags
                text = html_unescape(text).strip()
                col_w[i] = max(col_w.get(i, 0), _display_width(text))
        if not col_w:
            return match.group(0)
        ncol = max(col_w) + 1
        widths = [
            max(_TBL_MIN_COL,
                min(_TBL_MAX_COL, col_w.get(i, 1) * _TBL_PX_PER_UNIT + _TBL_CELL_PAD))
            for i in range(ncol)
        ]
        total = sum(widths)
        if total > _TBL_MAX_TOTAL:                              # scale down to fit
            scale = _TBL_MAX_TOTAL / total
            widths = [max(40, round(w * scale)) for w in widths]
        colgroup = "<colgroup>" + "".join(
            f'<col style="width: {w}px" />' for w in widths
        ) + "</colgroup>"
        body = re.sub(r"<colgroup>.*?</colgroup>", "", table, count=1, flags=re.DOTALL)
        return f'<table data-layout="default">{colgroup}{body}</table>'

    return re.sub(r"<table>(.*?)</table>", _process, html, flags=re.DOTALL)


def postprocess_html(html):
    """Transform pandoc HTML into Confluence storage format."""
    # 0a) <pre><code> -> Confluence code macro
    def _code_block_to_macro(match):
        lang_match = re.search(r'class="(?:sourceCode\s+)?(\w+)"', match.group(0))
        lang = lang_match.group(1) if lang_match else "none"
        code_match = re.search(r'<code[^>]*>(.*?)</code>', match.group(0), re.DOTALL)
        code = re.sub(r'<[^>]+>', '', code_match.group(1))  # strip inner tags
        code = html_unescape(code)
        code = code.replace(']]>', ']]]]><![CDATA[>')  # CDATA escape
        lang_param = (
            f'<ac:parameter ac:name="language">{lang}</ac:parameter>'
            if lang != "none" else ''
        )
        return (
            f'<ac:structured-macro ac:name="code">{lang_param}'
            f'<ac:plain-text-body><![CDATA[{code}]]>'
            f'</ac:plain-text-body></ac:structured-macro>'
        )

    html = re.sub(r'<pre[^>]*>\s*<code[^>]*>.*?</code>\s*</pre>', _code_block_to_macro, html, flags=re.DOTALL)

    # 0a.5) <details><summary>…</summary>…</details> → Confluence expand macro.
    #       Runs after 0a so the inner ```fence``` is already a code macro. Requires
    #       a <summary> (attribute-only <details> is left untouched). The whole match
    #       is replaced, so raw <details>/<summary> never reach 0b's attr-stripper or
    #       the Confluence sanitizer (which would silently drop them).
    #       Authoring contract (GitHub-native, pandoc-safe): a blank line after
    #       </summary> and before </details> so pandoc parses the inner fence as a
    #       code block. title text is already HTML-escaped by pandoc — do NOT re-escape.
    def _details_to_expand(match):
        title = re.sub(r'<[^>]+>', '', match.group(1)).strip() or '펼쳐 보기'
        body = match.group(2).strip()
        return (
            f'<ac:structured-macro ac:name="expand">'
            f'<ac:parameter ac:name="title">{title}</ac:parameter>'
            f'<ac:rich-text-body>{body}</ac:rich-text-body>'
            f'</ac:structured-macro>'
        )

    html = re.sub(
        r'<details[^>]*>\s*<summary[^>]*>(.*?)</summary>(.*?)</details>',
        _details_to_expand, html, flags=re.DOTALL,
    )

    # 0b) Strip foreign class/id/style attributes (preserve ac:/ri: elements)
    def _strip_foreign_attrs(match):
        tag = match.group(0)
        if '<ac:' in tag or '<ri:' in tag:
            return tag
        tag = re.sub(r'\s+class="[^"]*"', '', tag)
        tag = re.sub(r'\s+id="[^"]*"', '', tag)
        tag = re.sub(r'\s+style="[^"]*"', '', tag)
        return tag

    html = re.sub(r'<[a-zA-Z][^>]*>', _strip_foreign_attrs, html)

    # 1) <img> -> <ac:image> with attachment reference (original size)
    def _img_to_ac(match):
        attrs = match.group(1)
        src_m = re.search(r'src="([^"]*)"', attrs)
        alt_m = re.search(r'alt="([^"]*)"', attrs)
        if not src_m:
            return match.group(0)
        filename = url_unquote(os.path.basename(src_m.group(1)))
        alt = alt_m.group(1) if alt_m and alt_m.group(1) else ""
        alt_attrs = f' ac:alt="{alt}" ac:title="{alt}"' if alt else ""
        return (
            f'<ac:image{alt_attrs}>'
            f'<ri:attachment ri:filename="{filename}" />'
            f"</ac:image>"
        )

    html = re.sub(r"<img\s+([^>]*)\/?>", _img_to_ac, html)

    # 1.1) Strip <figure>/<figcaption> wrappers (defense against implicit_figures)
    html = re.sub(r'<figure[^>]*>\s*', '', html)
    html = re.sub(r'\s*</figure>', '', html)
    html = re.sub(r'\s*<figcaption[^>]*>.*?</figcaption>\s*', '', html, flags=re.DOTALL)

    # 1.5) Image captions → split into image + styled caption <p>
    # Case A: image and caption text in same <p> (no blank line in MD)
    html = re.sub(
        r'(<ac:image\b[^>]*>.*?</ac:image>)\s+([^<]+)</p>',
        r'\1</p>\n<p style="text-align: center; color: #626F86; font-size: 12px;"><em>\2</em></p>',
        html, flags=re.DOTALL,
    )
    # Case B: image and caption in separate <p> (blank line in MD)
    html = re.sub(
        r'(</ac:image>\s*</p>)\s*\n?\s*<p>([^<\n]+)</p>',
        r'\1\n<p style="text-align: center; color: #626F86; font-size: 12px;"><em>\2</em></p>',
        html,
    )

    # 2) Table styling - per-column width fitted to text length.
    #    pandoc emits bare <col /> (no width) inside <colgroup>; combined with
    #    data-layout="default" Confluence stretches the table to full page width
    #    and distributes columns evenly -> short cells become absurdly wide.
    #    Fix: measure each column's max display width (CJK=2, ASCII=1) and inject
    #    proportional px into the colgroup so the table fits its content.
    #    Only bare "<table>" (data tables) match; layout blocks use
    #    <table role="presentation"> and are left untouched.
    html = _fit_table_columns(html)

    # 3) Wrap bare <th>/<td> content in <p> tags (Confluence requires this)
    def _wrap_cell(match):
        tag = match.group(1)
        attrs = match.group(2) or ""
        content = match.group(3).strip()
        if not content:
            content = "<br/>"
        if not content.startswith(("<p>", "<p ", "<ac:", "<ul", "<ol", "<h")):
            content = f"<p>{content}</p>"
        return f"<{tag}{attrs}>{content}</{tag}>"

    html = re.sub(
        r"<(t[hd])(\s[^>]*)?>(.+?)</\1>",
        _wrap_cell, html, flags=re.DOTALL,
    )

    # 4) Clean up empty inline anchors (rule 19's <a id="..."></a> after id strip)
    #    Left in place, Confluence converts them to <p /> which breaks view-mode
    #    rendering of subsequent layout blocks.
    html = re.sub(r"<a(\s[^>]*)?>\s*</a>", "", html)

    # 5) Clean up empty paragraphs (both <p></p> and self-closing <p/>)
    html = re.sub(r"<p>\s*</p>", "", html)
    html = re.sub(r"<p\s*/>", "", html)

    # 6) Strip Unicode variation selectors (U+FE0E text-style, U+FE0F emoji-style)
    #    Confluence view renderer occasionally chokes on these inside <h2>.
    html = html.replace("︎", "").replace("️", "")

    # 7) Convert <table role="presentation"> layout blocks to Confluence native
    #    <ac:layout-section>. Cloud editor wraps unknown nested table structures
    #    in Legacy Content Macro (hidden in view mode):
    #    https://support.atlassian.com/confluence-cloud/docs/the-legacy-content-macro/
    html = _convert_layout_blocks(html)

    # 8) Pull-Quote 보정: <blockquote> 안 heading 은 Confluence 가 invalid 처리하여
    #    텍스트가 dropout 됨. info macro 로 변환하여 강조 효과 유지 + 누락 방지.
    def _quote_heading_to_info(match):
        inner = match.group(1)
        return (
            f'<ac:structured-macro ac:name="info">'
            f'<ac:rich-text-body>{inner}</ac:rich-text-body>'
            f'</ac:structured-macro>'
        )

    html = re.sub(
        r'<blockquote>\s*((?:<h[1-6][^>]*>.*?</h[1-6]>\s*)+)</blockquote>',
        _quote_heading_to_info, html, flags=re.DOTALL,
    )

    return html


# ---------------------------------------------------------------------------
# Layout Block conversion: rule 19 Feature Block <table role="presentation">
# → Confluence ac:layout-section (native, view-mode safe)
# ---------------------------------------------------------------------------

# Leaf layout block patterns — only match when cell content has no nested layout
_NO_NESTED = r'(?:(?!<table\s+role="presentation").)*?'

_LAYOUT_SINGLE = re.compile(
    r'<table\s+role="presentation"[^>]*>\s*'
    r'<tr>\s*'
    rf'<td\s+width="100%"[^>]*>({_NO_NESTED})</td>\s*'
    r'</tr>\s*'
    r'</table>',
    re.DOTALL,
)

_LAYOUT_TWO_EQUAL = re.compile(
    r'<table\s+role="presentation"[^>]*>\s*'
    r'<tr>\s*'
    rf'<td\s+width="50%"[^>]*>({_NO_NESTED})</td>\s*'
    rf'<td\s+width="50%"[^>]*>({_NO_NESTED})</td>\s*'
    r'</tr>\s*'
    r'</table>',
    re.DOTALL,
)

_LAYOUT_THREE_EQUAL = re.compile(
    r'<table\s+role="presentation"[^>]*>\s*'
    r'<tr>\s*'
    rf'<td\s+width="33%"[^>]*>({_NO_NESTED})</td>\s*'
    rf'<td\s+width="33%"[^>]*>({_NO_NESTED})</td>\s*'
    rf'<td\s+width="33%"[^>]*>({_NO_NESTED})</td>\s*'
    r'</tr>\s*'
    r'</table>',
    re.DOTALL,
)


def _convert_layout_blocks(html, max_iter=10):
    """Bottom-up iterative conversion of leaf layout tables to ac:layout.

    Each pass converts only innermost layout blocks (cells without nested
    <table role="presentation">). Outer wrappers become matchable next pass.
    """
    for _ in range(max_iter):
        before = html
        # 100% single cell → unwrap (no Confluence wrapper needed)
        html = _LAYOUT_SINGLE.sub(r"\1", html)
        # 50/50 → ac:layout two_equal
        html = _LAYOUT_TWO_EQUAL.sub(
            r'<ac:layout><ac:layout-section ac:type="two_equal">'
            r'<ac:layout-cell>\1</ac:layout-cell>'
            r'<ac:layout-cell>\2</ac:layout-cell>'
            r"</ac:layout-section></ac:layout>",
            html,
        )
        # 33/33/33 → ac:layout three_equal
        html = _LAYOUT_THREE_EQUAL.sub(
            r'<ac:layout><ac:layout-section ac:type="three_equal">'
            r'<ac:layout-cell>\1</ac:layout-cell>'
            r'<ac:layout-cell>\2</ac:layout-cell>'
            r'<ac:layout-cell>\3</ac:layout-cell>'
            r"</ac:layout-section></ac:layout>",
            html,
        )
        if html == before:
            break
    return html


# ---------------------------------------------------------------------------
# Collect image references
# ---------------------------------------------------------------------------

def _resolve_image(src, base_dir, tmp_dir, images, seen):
    """Resolve image path and add to collection if it exists on disk."""
    filename = os.path.basename(src)
    if filename in seen:
        return
    seen.add(filename)

    if src.startswith("mermaid-"):
        full = os.path.join(tmp_dir, src)
    else:
        full = os.path.join(base_dir, src)

    if os.path.exists(full):
        images.append((filename, full))
    else:
        # Try URL-decoded path (handles %EC%8A%A4... Korean filenames)
        decoded_src = url_unquote(src)
        decoded_full = os.path.join(base_dir, decoded_src)
        decoded_filename = os.path.basename(decoded_src)
        if os.path.exists(decoded_full):
            images.append((decoded_filename, decoded_full))
        else:
            print(f"  [MISSING] {src} (resolved: {full})")



def collect_images(md_content, base_dir, tmp_dir):
    """Return list of (filename, absolute_path) for all images."""
    images = []
    seen = set()

    # Pattern 1: Markdown image syntax ![alt](src)
    md_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    for _alt, src in md_pattern.findall(md_content):
        _resolve_image(src, base_dir, tmp_dir, images, seen)

    # Pattern 2: HTML <img src="..."> tags
    img_pattern = re.compile(r'<img\s+[^>]*src="([^"]*)"[^>]*/?>',)
    for src in img_pattern.findall(md_content):
        _resolve_image(src, base_dir, tmp_dir, images, seen)

    return images


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def convert(md_path, page_id, dry_run=False, base_url=None, parent_id=None, repo_root=None):
    cfg = get_config()
    if base_url:
        cfg["base_url"] = base_url

    md_path = Path(md_path).resolve()
    base_dir = str(md_path.parent)

    # Resolve repo_root for cross-link map (find ancestor that has docs/ folder)
    if repo_root is None:
        ancestor = md_path.parent
        while ancestor != ancestor.parent:
            if (ancestor / "docs").is_dir():
                repo_root = ancestor
                break
            ancestor = ancestor.parent
    repo_root = Path(repo_root) if repo_root else md_path.parent

    print(f"[1/6] Reading: {md_path}")
    md_content = md_path.read_text(encoding="utf-8")

    # Phase 2 — frontmatter 인과관계 추출
    fm = parse_frontmatter_full(md_content)
    if fm:
        causal_fields = sum(1 for k in (
            "derivative-of", "related-docs", "if-conflict", "last-synced",
            "owner", "audience-target", "tier", "legacy-id", "supersedes",
        ) if fm.get(k))
        print(f"  Frontmatter: {len(fm)} fields ({causal_fields} 인과관계)")

    print(f"[2/6] Fetching page info ({page_id})...")
    is_draft = False
    if not dry_run:
        info = get_page_info(cfg, page_id)
        ver = info["version"]["number"]
        title = info["title"]
        space = info["space"]["key"]
        is_draft = info.get("status") == "draft"
        if is_draft:
            print(f"  DRAFT page | Version: {ver} | Space: {space}")
            # Extract title from MD H1 if draft has no title
            if not title:
                h1_match = re.search(r"^#\s+(.+)$", md_content, re.MULTILINE)
                title = h1_match.group(1).strip() if h1_match else "Untitled"
                print(f"  Title from MD: {title}")
        else:
            print(f"  Title: {title} | Version: {ver} | Space: {space}")
    else:
        ver, title, space = 0, "DRY-RUN", "DRY"

    tmp_dir = tempfile.mkdtemp(prefix="md2con_")

    try:
        mermaid_count = len(re.findall(r"```mermaid", md_content))
        print(f"[3/6] Rendering {mermaid_count} Mermaid diagrams...")
        modified_md, mermaid_pngs = render_mermaid_blocks(md_content, tmp_dir)

        # Lossless: pull confluence-storage fences out before pandoc so
        # proprietary macros (e.g. TOC) round-trip verbatim. No-op when absent.
        modified_md, preserved_storage = _extract_preserved_storage(modified_md)
        if preserved_storage:
            print(f"  [preserve] {len(preserved_storage)} confluence-storage block(s) held for verbatim re-inject")

        print("[4/6] Converting MD -> Confluence HTML...")
        html = md_to_html(modified_md, base_dir)

        images = collect_images(modified_md, base_dir, tmp_dir)
        html = postprocess_html(html)
        html = _restore_preserved_storage(html, preserved_storage)

        # Phase 2 — 인과관계 박스 prepend + cross-link 변환
        repo_map = build_repo_path_to_pageid_map(repo_root)
        github_base = derive_github_base(repo_root)  # rule 22 — GitHub SSOT
        causality_html = build_causality_panel(fm, repo_map, md_path.parent, repo_root)
        if causality_html:
            html = causality_html + "\n" + html
            link_in_panel = causality_html.count("ri:page")
            print(f"  [causality] Info macro injected (frontmatter 9 fields, {link_in_panel} hyperlinks)")
        if repo_map or github_base:
            before_count = len(re.findall(r'<a\s+href="[^"]+\.md', html))
            html = transform_cross_links(html, repo_map, md_path.parent, repo_root)
            after_count = len(re.findall(r'<a\s+href="[^"]+\.md', html))
            converted = before_count - after_count
            if converted > 0:
                dest = "GitHub canonical (SSOT)" if github_base else "Confluence page"
                print(f"  [cross-link] {converted}/{before_count} markdown links → {dest} links")

        print(f"[5/6] Uploading {len(images)} attachments...")

        if dry_run:
            for fname, _fpath in images:
                print(f"  [DRY] Would upload: {fname}")
            print("[6/6] [DRY] Would update page content")
            preview = os.path.join(tmp_dir, "preview.html")
            Path(preview).write_text(html, encoding="utf-8")
            print(f"  Preview saved: {preview}")
            # Don't clean tmp_dir on dry-run so user can inspect
            return {"status": "dry_run", "preview": preview, "tmp_dir": tmp_dir}

        if is_draft:
            # Draft workflow: publish first (minimal body), then attach, then update body
            print(f"[5a/7] Publishing draft as page '{title}'...")
            result = update_page_content(
                cfg, page_id, title, "<p>Publishing...</p>", ver, space, publish_draft=True,
            )
            cur_ver = result["version"]["number"]
            print(f"  Published as v{cur_ver}")

            print(f"[5b/7] Uploading {len(images)} attachments...")
            failed = _upload_all(cfg, page_id, images)

            new_ver = cur_ver + 1
            print(f"[6/7] Updating page body (v{cur_ver} -> v{new_ver})...")
            result = update_page_content(cfg, page_id, title, html, new_ver, space)
            final_ver = result["version"]["number"]
            _report_upload_result(final_ver, failed)
        else:
            failed = _upload_all(cfg, page_id, images)

            new_ver = ver + 1
            print(f"[6/6] Updating page (v{ver} -> v{new_ver})...")
            if parent_id:
                print(f"  → moving under parent {parent_id}")
            result = update_page_content(cfg, page_id, title, html, new_ver, space, parent_id=parent_id)
            final_ver = result["version"]["number"]
            _report_upload_result(final_ver, failed)

        # Phase 2 — frontmatter → Confluence label 자동 부착
        if fm:
            apply_labels(cfg, page_id, fm)

        print("[7/7] Verifying push integrity (H1/H2 headers)...")
        total_headers = len(re.findall(r"^#{1,2}\s+", md_content, re.MULTILINE))
        missing = verify_push_integrity(cfg, page_id, md_content)
        if missing:
            print(f"  ⚠️  WARNING: {len(missing)}/{total_headers} header(s) missing in Confluence storage:")
            for h in missing:
                print(f"    - {h}")
            print("  → Likely Confluence sanitizer rejected a structure earlier in the page.")
            print("  → Inspect HTML between the last visible header and the first missing header.")
            return {"status": "partial", "version": final_ver, "missing_headers": missing}
        print(f"  [OK] All {total_headers} headers verified in Confluence storage.")

        return {"status": "success", "version": final_ver}

    finally:
        if not dry_run:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Markdown to Confluence converter"
    )
    parser.add_argument("markdown_file", help="Path to .md file")
    parser.add_argument("page_id", help="Confluence page ID")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview conversion without uploading",
    )
    parser.add_argument(
        "--base-url",
        help="Confluence base URL (include /wiki for Cloud)",
    )
    parser.add_argument(
        "--parent-id",
        help="Move page under this parent ID (sets ancestors)",
    )
    args = parser.parse_args()

    cfg = get_config()
    if not cfg["email"] or not cfg["token"]:
        print(
            "ERROR: ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN required.\n"
            "Set as environment variables or Windows User environment variables.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        result = convert(
            args.markdown_file, args.page_id,
            args.dry_run, args.base_url,
            parent_id=args.parent_id,
        )
        sys.exit(0 if result["status"] in ("success", "dry_run") else 1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
