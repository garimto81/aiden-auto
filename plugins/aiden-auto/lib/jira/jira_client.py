#!/usr/bin/env python3
"""jira_client - Jira REST API client library.

Handles: project info, board/epic analysis, issue search, bulk operations, ADF text extraction.

Usage:
    python jira_client.py project <key>
    python jira_client.py board <id>
    python jira_client.py epics <board_id>
    python jira_client.py search "<jql>"
    python jira_client.py issue <key>
    python jira_client.py close "<jql>"              # Bulk close by JQL
    python jira_client.py close-children <epic_key>  # Close all children of Epic
    python jira_client.py archive <key>
    python jira_client.py delete <key>

    Add --dry-run to close/close-children to preview without executing.

Environment:
    ATLASSIAN_EMAIL     - Jira user email
    ATLASSIAN_API_TOKEN - Jira API token
    JIRA_BASE_URL       - Base URL (default: https://ggnetwork.atlassian.net)
"""

import os
import sys
import json
import base64
import subprocess
import urllib.request
import urllib.parse
import urllib.error

sys.stdout.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _get_win_env(name):
    """Get Windows User environment variable (fallback when shell env is empty)."""
    try:
        import re
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name):
            return ""
        result = subprocess.run(
            ["powershell.exe", "-Command",
             f"[System.Environment]::GetEnvironmentVariable('{name}', 'User')"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_config():
    return {
        "base_url": (os.environ.get("JIRA_BASE_URL", "") or _get_win_env("JIRA_BASE_URL")
                     or "https://ggnetwork.atlassian.net"),
        "email": os.environ.get("ATLASSIAN_EMAIL", "") or _get_win_env("ATLASSIAN_EMAIL"),
        "token": os.environ.get("ATLASSIAN_API_TOKEN", "") or _get_win_env("ATLASSIAN_API_TOKEN"),
    }


def _auth_header(cfg):
    """Build Basic auth header from config."""
    cred = f"{cfg['email']}:{cfg['token']}"
    b64 = base64.b64encode(cred.encode()).decode()
    return f"Basic {b64}"


# ---------------------------------------------------------------------------
# Low-level REST helpers (urllib only)
# ---------------------------------------------------------------------------

def jira_get(path, params=None, cfg=None):
    """GET request to Jira REST API. Returns parsed JSON."""
    if cfg is None:
        cfg = get_config()

    url = f"{cfg['base_url']}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", _auth_header(cfg))
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        print(f"HTTP {e.code}: {path}\n{body}", file=sys.stderr)
        raise


def jira_request(path, method="PUT", body=None, cfg=None):
    """Send a non-GET request to Jira REST API. Returns parsed JSON or None."""
    if cfg is None:
        cfg = get_config()

    url = f"{cfg['base_url']}{path}"
    data = json.dumps(body).encode("utf-8") if body else None

    req = urllib.request.Request(url, method=method, data=data)
    req.add_header("Authorization", _auth_header(cfg))
    req.add_header("Accept", "application/json")
    if data:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")[:500]
        print(f"HTTP {e.code}: {method} {path}\n{body_text}", file=sys.stderr)
        raise


# ---------------------------------------------------------------------------
# Jira REST API functions
# ---------------------------------------------------------------------------

def get_project(project_key, cfg=None):
    """Get project details."""
    return jira_get(f"/rest/api/3/project/{project_key}", cfg=cfg)


def get_board(board_id, cfg=None):
    """Get board details."""
    return jira_get(f"/rest/agile/1.0/board/{board_id}", cfg=cfg)


def get_board_epics(board_id, cfg=None):
    """Get all epics for a board."""
    return jira_get(f"/rest/agile/1.0/board/{board_id}/epic", cfg=cfg)


def get_issue(issue_key, fields=None, cfg=None):
    """Get issue details."""
    params = {}
    if fields:
        params["fields"] = ",".join(fields) if isinstance(fields, list) else fields
    return jira_get(f"/rest/api/3/issue/{issue_key}", params=params or None, cfg=cfg)


def archive_issue(issue_key, cfg=None):
    """Archive a single issue. Uses Jira Cloud archive endpoint (Premium/Enterprise only)."""
    return jira_request(
        f"/rest/api/2/issue/{issue_key}/archive",
        method="PUT",
        cfg=cfg,
    )


def delete_issue(issue_key, cfg=None):
    """Permanently delete an issue. This action is irreversible."""
    return jira_request(
        f"/rest/api/3/issue/{issue_key}",
        method="DELETE",
        cfg=cfg,
    )


def transition_issue(issue_key, transition_id, cfg=None):
    """Transition an issue to a new status."""
    return jira_request(
        f"/rest/api/3/issue/{issue_key}/transitions",
        method="POST",
        body={"transition": {"id": str(transition_id)}},
        cfg=cfg,
    )


def update_issue(issue_key, fields, cfg=None):
    """Update issue fields (components, labels, etc.)."""
    return jira_request(
        f"/rest/api/3/issue/{issue_key}",
        method="PUT",
        body={"fields": fields},
        cfg=cfg,
    )


def search_issues(jql, max_results=50, fields=None, cfg=None):
    """Search issues via JQL (single page, up to max_results).

    Note: Use search_all_issues() for complete results with auto-pagination.
    """
    params = {"jql": jql, "maxResults": max(1, max_results)}
    if fields:
        params["fields"] = ",".join(fields) if isinstance(fields, list) else fields
    return jira_get("/rest/api/3/search/jql", params=params, cfg=cfg)


def search_all_issues(jql, fields=None, cfg=None):
    """Search issues with auto-pagination. Returns all matching issues."""
    if cfg is None:
        cfg = get_config()
    all_issues = []
    start = 0
    page_size = 100
    while True:
        params = {"jql": jql, "maxResults": page_size, "startAt": start}
        if fields:
            params["fields"] = ",".join(fields) if isinstance(fields, list) else fields
        data = jira_get("/rest/api/3/search/jql", params=params, cfg=cfg)
        issues = data.get("issues", [])
        all_issues.extend(issues)
        total = data.get("total", 0)
        if not issues or start + len(issues) >= total:
            break
        start += len(issues)
    return all_issues


def find_transition_id(issue_key, target_status, cfg=None):
    """Find transition ID for a target status name (case-insensitive).

    Queries the issue's available transitions and matches by destination status name.
    Returns transition ID string, or None if not found.
    """
    if cfg is None:
        cfg = get_config()
    data = jira_get(f"/rest/api/3/issue/{issue_key}/transitions", cfg=cfg)
    target_lower = target_status.lower()
    for t in data.get("transitions", []):
        to_name = t.get("to", {}).get("name", "")
        if to_name.lower() == target_lower:
            return t["id"]
    return None


def close_issues_by_jql(jql, dry_run=False, cfg=None):
    """Find all issues matching JQL and transition them to CLOSED.

    Auto-detects the correct CLOSED transition ID per issue.
    """
    if cfg is None:
        cfg = get_config()
    issues = search_all_issues(jql, fields=["summary", "status"], cfg=cfg)
    print(f"Found {len(issues)} issues matching query")
    if not issues:
        return []

    # Cache transition ID per project (usually same within a project)
    transition_cache = {}
    results = []
    for issue in issues:
        key = issue.get("key", "")
        summary = issue.get("fields", {}).get("summary", "")
        status = issue.get("fields", {}).get("status", {}).get("name", "")
        if dry_run:
            print(f"  [DRY] {key}  [{status}]  {summary}")
            results.append({"key": key, "action": "dry_run"})
            continue

        project = key.rsplit("-", 1)[0]
        if project not in transition_cache:
            tid = find_transition_id(key, "CLOSED", cfg=cfg)
            if not tid:
                tid = find_transition_id(key, "Closed", cfg=cfg)
            if not tid:
                tid = find_transition_id(key, "Done", cfg=cfg)
            transition_cache[project] = tid

        tid = transition_cache[project]
        if not tid:
            print(f"  SKIP  {key}  (no CLOSED/Done transition found)")
            results.append({"key": key, "action": "failed", "error": "no close transition"})
            continue

        try:
            transition_issue(key, tid, cfg=cfg)
            print(f"  OK    {key}  {summary}")
            results.append({"key": key, "action": "closed"})
        except Exception as e:
            print(f"  FAIL  {key}  {e}")
            results.append({"key": key, "action": "failed", "error": str(e)})
    return results


def _validate_issue_key(key: str) -> str:
    """Validate and sanitize Jira issue key to prevent JQL injection."""
    import re
    if not re.match(r'^[A-Z][A-Z0-9]+-\d+$', key):
        raise ValueError(f"Invalid Jira issue key format: {key}")
    return key


def close_children(epic_key, dry_run=False, cfg=None):
    """Close all non-Epic child issues under an Epic."""
    epic_key = _validate_issue_key(epic_key)
    jql = f'parent = {epic_key} AND issuetype != Epic AND status != CLOSED AND status != Done'
    print(f"Closing children of {epic_key}...")
    return close_issues_by_jql(jql, dry_run=dry_run, cfg=cfg)


# ---------------------------------------------------------------------------
# ADF (Atlassian Document Format) -> plain text
# ---------------------------------------------------------------------------

def extract_adf_text(node, depth=0):
    """Convert ADF JSON node to structured plain text.

    Handles: text, heading, paragraph, bulletList, orderedList, listItem,
    codeBlock, blockquote, strong/em marks.
    """
    if node is None:
        return ""

    if isinstance(node, str):
        return node

    node_type = node.get("type", "")
    text = node.get("text", "")

    # Apply marks (bold, italic, etc.)
    if text and node.get("marks"):
        for mark in node["marks"]:
            if mark["type"] == "strong":
                text = f"**{text}**"
            elif mark["type"] == "em":
                text = f"_{text}_"
            elif mark["type"] == "code":
                text = f"`{text}`"
            elif mark["type"] == "link":
                href = mark.get("attrs", {}).get("href", "")
                text = f"[{text}]({href})" if href else text

    if node_type == "text":
        return text

    # Collect children text
    content = node.get("content", [])
    children_text = "".join(extract_adf_text(child, depth) for child in content)

    indent = "  " * depth

    if node_type == "heading":
        level = node.get("attrs", {}).get("level", 1)
        prefix = "#" * level
        return f"\n{prefix} {children_text}\n"

    if node_type == "paragraph":
        return f"{indent}{children_text}\n"

    if node_type == "bulletList":
        items = []
        for child in content:
            item_text = extract_adf_text(child, depth + 1).strip()
            items.append(f"{indent}- {item_text}")
        return "\n".join(items) + "\n"

    if node_type == "orderedList":
        items = []
        for i, child in enumerate(content, 1):
            item_text = extract_adf_text(child, depth + 1).strip()
            items.append(f"{indent}{i}. {item_text}")
        return "\n".join(items) + "\n"

    if node_type == "listItem":
        return children_text

    if node_type == "codeBlock":
        lang = node.get("attrs", {}).get("language", "")
        return f"\n```{lang}\n{children_text}```\n"

    if node_type == "blockquote":
        lines = children_text.strip().split("\n")
        return "\n".join(f"> {line}" for line in lines) + "\n"

    if node_type == "rule":
        return "\n---\n"

    if node_type in ("doc", "mediaSingle", "media", "table", "tableRow",
                      "tableCell", "tableHeader", "panel", "expand"):
        return children_text

    # Fallback: return children text
    return children_text


# ---------------------------------------------------------------------------
# Epic analysis
# ---------------------------------------------------------------------------

def analyze_epics(board_id, cfg=None):
    """Get all epics for a board, extract descriptions, count stories."""
    if cfg is None:
        cfg = get_config()

    print(f"[1/3] Fetching board {board_id}...")
    board = get_board(board_id, cfg)
    print(f"  Board: {board.get('name', 'N/A')} (project: {board.get('location', {}).get('projectKey', 'N/A')})")

    print("[2/3] Fetching epics...")
    epics_data = get_board_epics(board_id, cfg)
    epics = epics_data.get("values", [])
    print(f"  Found {len(epics)} epics")

    print("[3/3] Analyzing each epic...\n")
    print("=" * 70)

    # Batch fetch descriptions (N calls → 1 call)
    desc_map = {}
    epic_keys = [e.get("key") for e in epics if e.get("key")]
    if epic_keys:
        try:
            validated_keys = [_validate_issue_key(k) for k in epic_keys]
            keys_jql = ", ".join(validated_keys)
            batch = search_issues(
                f"key in ({keys_jql})",
                max_results=len(epic_keys),
                fields=["description", "summary", "status"],
                cfg=cfg,
            )
            for issue in batch.get("issues", []):
                desc_map[issue["key"]] = issue.get("fields", {}).get("description")
        except Exception as e:
            print(f"  [WARN] Batch description fetch failed, falling back: {e}")

    for epic in epics:
        epic_key = epic.get("key", "N/A")
        epic_name = epic.get("name", "") or epic.get("summary", "N/A")
        status = epic.get("status", {}).get("name", "N/A") if isinstance(epic.get("status"), dict) else "N/A"
        done = epic.get("done", False)

        print(f"\n{'=' * 70}")
        print(f"EPIC: {epic_key} - {epic_name}")
        print(f"Status: {status} | Done: {done}")
        print(f"{'-' * 70}")

        # Use batched description (fallback to individual fetch)
        desc = desc_map.get(epic_key)
        if desc is None and epic_key not in desc_map:
            try:
                full = get_issue(epic_key, fields=["description"], cfg=cfg)
                desc = full.get("fields", {}).get("description")
            except Exception as e:
                print(f"  [WARN] Could not fetch details: {e}")
        if desc:
            print("\nDescription:")
            print(extract_adf_text(desc))
        else:
            print("\n(No description)")

        # Count child stories
        try:
            validated_key = _validate_issue_key(epic_key)
            children = search_issues(
                f'"Epic Link" = {validated_key}',
                max_results=1,
                fields=["summary"],
                cfg=cfg,
            )
            total = children.get("total", 0)
            print(f"Stories/Sub-tasks: {total}")
        except Exception:
            print("Stories/Sub-tasks: (query failed)")

    print(f"\n{'=' * 70}")
    print(f"Total epics: {len(epics)}")
    return epics


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()
    target = sys.argv[2]
    cfg = get_config()

    if not cfg["email"] or not cfg["token"]:
        print("ERROR: ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN required.", file=sys.stderr)
        print("Set them as environment variables or Windows User env vars.", file=sys.stderr)
        sys.exit(1)

    try:
        if command == "project":
            data = get_project(target, cfg)
            print(f"Project: {data.get('key')} - {data.get('name')}")
            print(f"ID: {data.get('id')}")
            print(f"Style: {data.get('style', 'N/A')}")
            lead = data.get("lead", {})
            print(f"Lead: {lead.get('displayName', 'N/A')}")
            print(f"URL: {cfg['base_url']}/browse/{data.get('key')}")

        elif command == "board":
            data = get_board(target, cfg)
            print(f"Board: {data.get('name')}")
            print(f"ID: {data.get('id')}")
            print(f"Type: {data.get('type', 'N/A')}")
            loc = data.get("location", {})
            print(f"Project: {loc.get('projectKey', 'N/A')} - {loc.get('displayName', 'N/A')}")

        elif command == "epics":
            analyze_epics(target, cfg)

        elif command == "search":
            jql = target
            fields_arg = sys.argv[3] if len(sys.argv) > 3 else "summary,status,issuetype"
            issues = search_all_issues(jql, fields=fields_arg, cfg=cfg)
            print(f"Results: {len(issues)} total\n")
            for issue in issues:
                key = issue.get("key", "")
                fields_data = issue.get("fields", {})
                summary = fields_data.get("summary", "N/A")
                status = fields_data.get("status", {}).get("name", "N/A")
                itype = fields_data.get("issuetype", {}).get("name", "N/A")
                print(f"  [{key}] ({itype}) {summary}  [{status}]")

        elif command == "issue":
            data = get_issue(target, cfg=cfg)
            fields_data = data.get("fields", {})
            print(f"Issue: {data.get('key')} - {fields_data.get('summary', 'N/A')}")
            print(f"Type: {fields_data.get('issuetype', {}).get('name', 'N/A')}")
            print(f"Status: {fields_data.get('status', {}).get('name', 'N/A')}")
            print(f"Priority: {fields_data.get('priority', {}).get('name', 'N/A')}")
            assignee = fields_data.get("assignee")
            print(f"Assignee: {assignee.get('displayName', 'N/A') if assignee else 'Unassigned'}")
            print(f"URL: {cfg['base_url']}/browse/{data.get('key')}")

            desc = fields_data.get("description")
            if desc:
                print(f"\n{'=' * 50}")
                print("Description:")
                print(extract_adf_text(desc))

        elif command == "close":
            jql = target
            dry_run = "--dry-run" in sys.argv
            results = close_issues_by_jql(jql, dry_run=dry_run, cfg=cfg)
            ok = sum(1 for r in results if r["action"] == "closed")
            fail = sum(1 for r in results if r["action"] == "failed")
            dry = sum(1 for r in results if r["action"] == "dry_run")
            if dry_run:
                print(f"\n[DRY RUN] {dry} issues would be closed")
            else:
                print(f"\nResult: {ok} closed, {fail} failed")

        elif command == "close-children":
            dry_run = "--dry-run" in sys.argv
            results = close_children(target, dry_run=dry_run, cfg=cfg)
            ok = sum(1 for r in results if r["action"] == "closed")
            fail = sum(1 for r in results if r["action"] == "failed")
            dry = sum(1 for r in results if r["action"] == "dry_run")
            if dry_run:
                print(f"\n[DRY RUN] {dry} children would be closed")
            else:
                print(f"\nResult: {ok} closed, {fail} failed")

        elif command == "archive":
            archive_issue(target, cfg)
            print(f"Archived: {target}")

        elif command == "delete":
            delete_issue(target, cfg)
            print(f"Deleted: {target}")

        else:
            print(f"Unknown command: {command}", file=sys.stderr)
            print("Commands: project, board, epics, search, issue, close, close-children, archive, delete", file=sys.stderr)
            sys.exit(1)

    except urllib.error.HTTPError as e:
        print(f"ERROR: HTTP {e.code}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
