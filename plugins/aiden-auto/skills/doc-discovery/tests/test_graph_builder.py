"""Self-verification suite for Layer 1 graph builder.

Run directly: python tests/test_graph_builder.py
Or with pytest: pytest tests/ -v

Builds a fixture project that mirrors the real-world incident
(Overview.md change → derivative PRDs become stale) and asserts the
graph traversal correctly identifies all impacted files.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# resolve sibling lib/
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from lib.graph_builder import (  # noqa: E402
    build_graph,
    impact_analysis,
    parse_frontmatter,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_fixture(root: Path) -> None:
    """Recreate the Command_Center_PRD incident scenario in miniature.

    Overview.md is the source. Three direct derivatives + one transitive
    derivative + one supersedes edge + one weak link should all be detected.
    """
    _write(
        root / "docs/00-prd/Overview.md",
        "---\ntitle: Overview\n---\n\nRoot doc.\n",
    )
    _write(
        root / "docs/00-prd/Command_Center_PRD.md",
        "---\ntitle: Command Center\nderivative-of: Overview.md\n---\n\nDerived from Overview.\n",
    )
    _write(
        root / "docs/00-prd/Foundation_PRD.md",
        "---\ntitle: Foundation\nderivative-of:\n  - Overview.md\n  - Auth_PRD.md\n---\n\nDerived from two roots.\n",
    )
    _write(
        root / "docs/00-prd/Auth_PRD.md",
        "---\ntitle: Auth\nderivative-of: Overview.md\n---\n\nDerived.\n",
    )
    # transitive: Auth_API_Spec → Auth_PRD → Overview
    _write(
        root / "docs/00-prd/Auth_API_Spec.md",
        "---\ntitle: Auth API\nderivative-of: Auth_PRD.md\n---\n\nTransitive child.\n",
    )
    # supersedes edge
    _write(
        root / "docs/00-prd/Old_Overview.md",
        "---\ntitle: Old Overview\nsupersedes: Overview.md\n---\n\nReplaces Overview.\n",
    )
    # weak link in body
    _write(
        root / ".claude/rules/00-foo.md",
        "---\ntitle: Foo Rule\n---\n\nSee [Overview](../../docs/00-prd/Overview.md) for context.\n",
    )
    # unrelated file — must NOT appear in impact
    _write(
        root / "docs/00-prd/Unrelated.md",
        "---\ntitle: Unrelated\n---\n\nNothing to do with Overview.\n",
    )


# ─────────────────────────── tests ────────────────────────────

def test_frontmatter_parses_single_value():
    text = "---\nderivative-of: Overview.md\n---\nbody"
    fm = parse_frontmatter(text)
    assert fm.get("derivative-of") == "Overview.md", fm


def test_frontmatter_parses_list():
    text = "---\nderivative-of:\n  - A.md\n  - B.md\n---\nbody"
    fm = parse_frontmatter(text)
    val = fm.get("derivative-of")
    assert val == ["A.md", "B.md"], val


def test_frontmatter_parses_inline_list():
    text = "---\nderivative-of: [A.md, B.md]\n---\nbody"
    fm = parse_frontmatter(text)
    val = fm.get("derivative-of")
    assert val == ["A.md", "B.md"], val


def test_frontmatter_absent_returns_empty():
    assert parse_frontmatter("no frontmatter here") == {}


def test_graph_finds_direct_dependents(root: Path):
    graph = build_graph(root)
    report = impact_analysis(graph, "docs/00-prd/Overview.md", transitive=False)
    direct_set = set(report["direct"])
    expected_direct = {
        "docs/00-prd/Command_Center_PRD.md",
        "docs/00-prd/Foundation_PRD.md",
        "docs/00-prd/Auth_PRD.md",
        "docs/00-prd/Old_Overview.md",  # supersedes
        ".claude/rules/00-foo.md",       # link
    }
    assert expected_direct.issubset(direct_set), (
        f"direct miss. expected ⊆ got. expected={expected_direct} got={direct_set}"
    )


def test_graph_finds_transitive_dependents(root: Path):
    graph = build_graph(root)
    report = impact_analysis(graph, "docs/00-prd/Overview.md", transitive=True)
    all_files = set(report["direct"])
    for depth_files in report["transitive"].values():
        all_files.update(depth_files)
    assert "docs/00-prd/Auth_API_Spec.md" in all_files, (
        f"transitive (Auth_API_Spec via Auth_PRD) missed. got={all_files}"
    )


def test_unrelated_file_not_in_impact(root: Path):
    graph = build_graph(root)
    report = impact_analysis(graph, "docs/00-prd/Overview.md", transitive=True)
    all_files = set(report["direct"])
    for depth_files in report["transitive"].values():
        all_files.update(depth_files)
    assert "docs/00-prd/Unrelated.md" not in all_files, (
        "false positive: unrelated file appeared in impact"
    )


def test_total_count_excludes_target_itself(root: Path):
    graph = build_graph(root)
    report = impact_analysis(graph, "docs/00-prd/Overview.md")
    # target itself should not be counted
    assert report["target"] not in report["direct"]


def test_no_transitive_excludes_depth_2(root: Path):
    graph = build_graph(root)
    report = impact_analysis(graph, "docs/00-prd/Overview.md", transitive=False)
    assert report["transitive"] == {}, (
        f"--no-transitive should yield empty transitive map. got={report['transitive']}"
    )


def test_cli_text_format(root: Path, script_path: Path):
    result = subprocess.run(
        [sys.executable, str(script_path), "--impact-of", "docs/00-prd/Overview.md", "--root", str(root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 1, f"expected exit 1 (impact found), got {result.returncode}: {result.stderr}"
    assert "IMPACT" in result.stdout
    assert "Command_Center_PRD.md" in result.stdout


def test_cli_json_format(root: Path, script_path: Path):
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--impact-of",
            "docs/00-prd/Overview.md",
            "--root",
            str(root),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["target"] == "docs/00-prd/Overview.md"
    assert payload["total_affected"] >= 5  # 4 direct PRDs + 1 rule + transitive


def test_cli_no_impact_for_unreferenced_file(root: Path, script_path: Path):
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--impact-of",
            "docs/00-prd/Unrelated.md",
            "--root",
            str(root),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    # Old_Overview supersedes Overview (not Unrelated). Unrelated should be safe.
    assert result.returncode == 0, f"expected exit 0 (no impact), got {result.returncode}: {result.stdout}"
    assert "OK" in result.stdout


# ─────────────────── runner (no pytest required) ────────────────────

def _run_all() -> int:
    failures = []

    # frontmatter unit tests (no fixture)
    for fn in (
        test_frontmatter_parses_single_value,
        test_frontmatter_parses_list,
        test_frontmatter_parses_inline_list,
        test_frontmatter_absent_returns_empty,
    ):
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            failures.append((fn.__name__, str(e)))
            print(f"FAIL  {fn.__name__}: {e}")

    # fixture-backed tests
    with tempfile.TemporaryDirectory(prefix="docdiscov_") as tmp:
        root = Path(tmp)
        make_fixture(root)
        script = HERE.parent / "scripts" / "doc_discovery.py"

        for fn in (
            test_graph_finds_direct_dependents,
            test_graph_finds_transitive_dependents,
            test_unrelated_file_not_in_impact,
            test_total_count_excludes_target_itself,
            test_no_transitive_excludes_depth_2,
        ):
            try:
                fn(root)
                print(f"PASS  {fn.__name__}")
            except AssertionError as e:
                failures.append((fn.__name__, str(e)))
                print(f"FAIL  {fn.__name__}: {e}")

        for fn in (
            test_cli_text_format,
            test_cli_json_format,
            test_cli_no_impact_for_unreferenced_file,
        ):
            try:
                fn(root, script)
                print(f"PASS  {fn.__name__}")
            except AssertionError as e:
                failures.append((fn.__name__, str(e)))
                print(f"FAIL  {fn.__name__}: {e}")

    print("─" * 60)
    if failures:
        print(f"FAILED  {len(failures)} test(s)")
        for name, err in failures:
            print(f"  · {name}: {err}")
        return 1
    print(f"OK  all tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(_run_all())
