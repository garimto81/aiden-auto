#!/usr/bin/env python3
"""confluence_bidi_sync - bidirectional Markdown <-> Confluence orchestrator.

Per tracked document (frontmatter has confluence-page-id / confluence-url):

    1. fetch live Confluence storage + version
    2. confluence2md -> theirs_md
    3. classify drift vs the last-synced base  (4-case)
    4. act:  neither -> noop
             only-local  -> push (md2confluence)
             only-remote -> pull (write local, frontmatter preserved)
             both        -> 3-way merge  (CLEAN -> write+push / CONFLICT -> stop)
    5. update base snapshot + manifest

Scope is frontmatter-driven (md2confluence.build_repo_path_to_pageid_map) — no
hardcoded doc list, device-agnostic.

State (committed sidecar, repo-shared so 3-way works across machines):
    docs/.confluence-sync/manifest.json
    docs/.confluence-sync/base/<page_id>.md

Default is --dry-run (report decisions only); --apply performs writes/pushes.
Pure decision functions (split_body / classify_drift / manifest I/O) are unit
tested; the network/orchestration layer reuses md2confluence helpers.
"""

import argparse
import json
import sys
from pathlib import Path

import md2confluence as m2c
import confluence2md as c2m
import threeway as tw

SIDECAR_DIRNAME = ".confluence-sync"

NEITHER = "neither"
ONLY_LOCAL = "only-local"
ONLY_REMOTE = "only-remote"
BOTH = "both"
BOOTSTRAP = "bootstrap"


# ---------------------------------------------------------------------------
# Frontmatter-aware body handling
# ---------------------------------------------------------------------------

def frontmatter_block(md):
    """Return the leading '---\\n...\\n---\\n' block (with delimiters) or ''."""
    if md.startswith("---\n"):
        end = md.find("\n---\n", 4)
        if end != -1:
            return md[: end + 5]
    return ""


def split_body(md):
    """Return body (everything after the frontmatter block)."""
    fm = frontmatter_block(md)
    return md[len(fm):] if fm else md


def merge_frontmatter(local_md, new_body):
    """Keep local frontmatter, swap in new body (pull never overwrites fm)."""
    fm = frontmatter_block(local_md)
    return fm + new_body if fm else new_body


# ---------------------------------------------------------------------------
# Drift classification (4-case) — cosmetic-tolerant
# ---------------------------------------------------------------------------

def classify_drift(local_body, base_body, theirs_body, live_version, base_version):
    """Return one of NEITHER / ONLY_LOCAL / ONLY_REMOTE / BOTH.

    remote_changed requires BOTH a version bump AND a real (normalized) content
    difference — Confluence re-formats stored XHTML on save, so a version bump
    alone is not proof of a human edit (cosmetic 거짓 drift guard).
    """
    n = tw.normalize_for_compare
    nlocal, nbase, ntheirs = n(local_body), n(base_body), n(theirs_body)
    local_changed = nlocal != nbase
    remote_changed = (live_version != base_version) and (ntheirs != nbase)
    if not local_changed and not remote_changed:
        return NEITHER
    if local_changed and not remote_changed:
        return ONLY_LOCAL
    if remote_changed and not local_changed:
        return ONLY_REMOTE
    return BOTH


# ---------------------------------------------------------------------------
# Manifest + base snapshot store
# ---------------------------------------------------------------------------

def sidecar_dir(repo_root):
    return Path(repo_root) / "docs" / SIDECAR_DIRNAME


def manifest_path(repo_root):
    return sidecar_dir(repo_root) / "manifest.json"


def load_manifest(repo_root):
    p = manifest_path(repo_root)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"schema": 1, "entries": {}}


def save_manifest(repo_root, data):
    p = manifest_path(repo_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def base_file(repo_root, page_id):
    return sidecar_dir(repo_root) / "base" / f"{page_id}.md"


def read_base(repo_root, page_id):
    p = base_file(repo_root, page_id)
    return p.read_text(encoding="utf-8") if p.exists() else None


def write_base(repo_root, page_id, body):
    p = base_file(repo_root, page_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


# ---------------------------------------------------------------------------
# Per-document planning (pure: given inputs, decide the action)
# ---------------------------------------------------------------------------

def plan_document(local_md, base_body, theirs_md, live_version, base_version, ledger):
    """Decide the action + merge result for one document. Network-free.

    Returns dict: {action, status, merged_body?, conflict?, warnings[]}.
    """
    warnings = []
    if ledger and ledger.get("dropped"):
        warnings.append(f"confluence2md dropped macros: {ledger['dropped']}")

    local_body = split_body(local_md)
    theirs_body = split_body(theirs_md) if frontmatter_block(theirs_md) else theirs_md

    # Bootstrap: no base recorded yet → adopt current local, no destructive merge.
    if base_body is None:
        return {"action": BOOTSTRAP, "status": "ok",
                "merged_body": local_body, "warnings": warnings}

    case = classify_drift(local_body, base_body, theirs_body, live_version, base_version)

    if case == NEITHER:
        return {"action": NEITHER, "status": "in-sync", "warnings": warnings}
    if case == ONLY_LOCAL:
        return {"action": ONLY_LOCAL, "status": "push",
                "merged_body": local_body, "warnings": warnings}
    if case == ONLY_REMOTE:
        return {"action": ONLY_REMOTE, "status": "pull",
                "merged_body": theirs_body, "warnings": warnings}

    # BOTH → 3-way merge (body only; frontmatter is ours-fixed)
    status, merged = tw.merge_texts(local_body, base_body, theirs_body)
    if status == tw.CONFLICT:
        return {"action": BOTH, "status": "conflict",
                "merged_body": merged, "conflict": True, "warnings": warnings}
    return {"action": BOTH, "status": "merged",
            "merged_body": merged, "conflict": False, "warnings": warnings}


# ---------------------------------------------------------------------------
# Network layer (reuses md2confluence helpers)
# ---------------------------------------------------------------------------

def fetch_storage(cfg, page_id):
    """Return (storage_xhtml, version_number)."""
    info = m2c.api_get(cfg, f"/content/{page_id}", {"expand": "body.storage,version"})
    return info["body"]["storage"]["value"], info["version"]["number"]


def build_link_resolver(repo_map):
    """Invert repo_map {relpath:(page_id,title,url)} -> {title: relpath}."""
    out = {}
    for rel, entry in repo_map.items():
        if "/" not in rel and "\\" not in rel:
            continue  # skip basename-only duplicate keys
        _pid, title, _url = entry
        if title:
            out.setdefault(title, rel)
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def discover_targets(repo_root):
    """Frontmatter-driven scope: {relpath: page_id} for docs with a page-id."""
    repo_map = m2c.build_repo_path_to_pageid_map(repo_root)
    targets = {}
    for rel, (page_id, _title, url) in repo_map.items():
        if "/" not in rel:        # skip basename duplicate keys
            continue
        # Need an explicit page_id to pull/push; derive from URL if needed.
        pid = page_id
        if not pid and url:
            import re
            m = re.search(r"/pages/(\d+)", url)
            pid = m.group(1) if m else ""
        if pid:
            targets[rel] = pid
    return targets, repo_map


def sync_one(cfg, repo_root, rel, page_id, repo_map, manifest, apply):
    """Sync a single document. Returns a result dict for reporting."""
    local_path = Path(repo_root) / rel
    local_md = local_path.read_text(encoding="utf-8")

    # Conflict-marker guard: never push a half-resolved file.
    if tw.has_conflict_markers(local_md):
        return {"rel": rel, "action": "skip", "status": "unresolved-conflict",
                "warnings": ["local file has unresolved <<<<<<< merge markers"]}

    storage, live_version = fetch_storage(cfg, page_id)
    link_resolver = build_link_resolver(repo_map)
    theirs_md, ledger = c2m.confluence_to_md(storage, link_resolver=link_resolver)

    entry = manifest.get("entries", {}).get(rel, {})
    base_version = entry.get("confluence_version")
    base_body = read_base(repo_root, page_id)

    plan = plan_document(local_md, base_body, theirs_md, live_version, base_version, ledger)
    plan["rel"] = rel
    plan["page_id"] = page_id

    if not apply:
        return plan

    action = plan["action"]
    merged_body = plan.get("merged_body")

    if action == NEITHER:
        return plan

    if action == "conflict" or plan.get("conflict"):
        # Write merged-with-markers locally, hold push, escalate.
        local_path.write_text(merge_frontmatter(local_md, merged_body), encoding="utf-8")
        return plan

    if action == ONLY_REMOTE:
        local_path.write_text(merge_frontmatter(local_md, merged_body), encoding="utf-8")
    elif action in (ONLY_LOCAL, BOTH, BOOTSTRAP):
        if action in (BOTH,):
            local_path.write_text(merge_frontmatter(local_md, merged_body), encoding="utf-8")
        # push current local (now == merged) to Confluence
        m2c.convert(str(local_path), page_id, dry_run=False, repo_root=repo_root)

    # Update base snapshot + manifest (success path)
    _storage2, new_version = fetch_storage(cfg, page_id)
    new_local = local_path.read_text(encoding="utf-8")
    write_base(repo_root, page_id, split_body(new_local))
    manifest.setdefault("entries", {})[rel] = {
        "page_id": page_id,
        "confluence_version": new_version,
        "base_sha": tw.sha256_text(split_body(new_local)),
        "synced_at": entry.get("synced_at", ""),
    }
    return plan


def run(repo_root, apply=False, only=None):
    cfg = m2c.get_config()
    targets, repo_map = discover_targets(repo_root)
    if only:
        targets = {k: v for k, v in targets.items() if k in only}
    manifest = load_manifest(repo_root)
    results = []
    conflicts = 0
    for rel, page_id in sorted(targets.items()):
        try:
            res = sync_one(cfg, repo_root, rel, page_id, repo_map, manifest, apply)
        except Exception as e:
            res = {"rel": rel, "action": "error", "status": str(e), "warnings": []}
        results.append(res)
        if res.get("conflict") or res.get("status") in ("conflict", "unresolved-conflict"):
            conflicts += 1
        _print_result(res, apply)
    if apply:
        save_manifest(repo_root, manifest)
    return results, conflicts


def _print_result(res, apply):
    rel = res.get("rel", "?")
    status = res.get("status", "?")
    tag = "APPLY" if apply else "DRY"
    print(f"  [{tag}] {rel}: {res.get('action')} ({status})")
    for w in res.get("warnings", []):
        print(f"        ⚠ {w}")


def main():
    parser = argparse.ArgumentParser(description="Bidirectional Markdown <-> Confluence sync")
    parser.add_argument("--repo-root", default=".", help="Repo root (contains docs/)")
    parser.add_argument("--apply", action="store_true", help="Perform writes/pushes (default: dry-run)")
    parser.add_argument("--only", nargs="*", help="Restrict to these repo-relative paths")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    cfg = m2c.get_config()
    if args.apply and (not cfg["email"] or not cfg["token"]):
        print("ERROR: ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN required for --apply.", file=sys.stderr)
        sys.exit(1)

    _results, conflicts = run(repo_root, apply=args.apply, only=args.only)
    if conflicts:
        print(f"\n⚠ {conflicts} document(s) need manual conflict resolution.")
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
