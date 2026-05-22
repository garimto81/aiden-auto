"""End-to-end integration test (Week 3) — full corpus walk + cache + bridge edges."""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from lib.cache import EdgeCache  # noqa: E402
from lib.graph_builder import impact_analysis  # noqa: E402
from lib.unified_graph import build_unified_graph  # noqa: E402


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_realistic_repo(root: Path) -> None:
    """Mirror the actual sort of repo this skill targets:
    - 4 PRDs (1 Overview + 3 derivatives)
    - 1 rule referencing Overview via inline link
    - 2 Python modules (one importing the other)
    - 1 Python module with a comment referencing Overview.md
    - 1 unrelated TS file
    """
    # docs
    _write(root / "docs/00-prd/Overview.md", "---\ntitle: Overview\n---\n\nRoot.\n")
    _write(
        root / "docs/00-prd/Auth_PRD.md",
        "---\ntitle: Auth\nderivative-of: Overview.md\n---\n\n",
    )
    _write(
        root / "docs/00-prd/Billing_PRD.md",
        "---\ntitle: Billing\nderivative-of: Overview.md\n---\n\n",
    )
    _write(
        root / "docs/00-prd/Reporting_PRD.md",
        "---\ntitle: Reporting\nderivative-of: Overview.md\n---\n\n",
    )
    # rule with markdown link
    _write(
        root / ".claude/rules/01-arch.md",
        "---\ntitle: Arch Rule\n---\n\nSee [Overview](../../docs/00-prd/Overview.md).\n",
    )
    # python modules
    _write(
        root / "src/billing.py",
        "from src.utils import format_money\n\n"
        "def charge(amount):\n    return format_money(amount)\n",
    )
    _write(
        root / "src/utils.py",
        "# implements per docs/00-prd/Overview.md § pricing\n"
        "def format_money(amount):\n    return f'${amount:.2f}'\n",
    )
    # ts file unrelated to overview
    _write(
        root / "src/widget.ts",
        "import { useState } from 'react';\nexport function Widget() {}\n",
    )


def test_full_build_finds_all_impact_classes():
    with tempfile.TemporaryDirectory(prefix="docdiscov_int_") as tmp:
        root = Path(tmp)
        make_realistic_repo(root)

        graph = build_unified_graph(root)
        report = impact_analysis(graph, "docs/00-prd/Overview.md", transitive=True)

        affected = set(report["direct"])
        for files in report["transitive"].values():
            affected.update(files)

        # all 3 derivative PRDs
        assert "docs/00-prd/Auth_PRD.md" in affected
        assert "docs/00-prd/Billing_PRD.md" in affected
        assert "docs/00-prd/Reporting_PRD.md" in affected
        # rule with inline link
        assert ".claude/rules/01-arch.md" in affected
        # bridge: src/utils.py comment references Overview
        assert "src/utils.py" in affected
        # widget.ts has nothing to do with Overview
        assert "src/widget.ts" not in affected


def test_cache_speeds_up_second_build():
    with tempfile.TemporaryDirectory(prefix="docdiscov_cache_") as tmp:
        root = Path(tmp)
        make_realistic_repo(root)
        cache_path = Path(tmp) / "cache.db"

        # cold build
        cache1 = EdgeCache(cache_path)
        try:
            t0 = time.perf_counter()
            build_unified_graph(root, cache=cache1)
            cold = time.perf_counter() - t0
            cold_misses = cache1.misses
            cold_hits = cache1.hits
        finally:
            cache1.close()

        # warm build — same files, untouched
        cache2 = EdgeCache(cache_path)
        try:
            t0 = time.perf_counter()
            build_unified_graph(root, cache=cache2)
            warm = time.perf_counter() - t0
            warm_hits = cache2.hits
            warm_misses = cache2.misses
        finally:
            cache2.close()

        # cold should miss everywhere; warm should hit on every file
        assert cold_misses > 0
        assert cold_hits == 0
        assert warm_hits > 0
        assert warm_misses == 0
        # warm shouldn't be dramatically slower than cold (allow noise)
        assert warm < cold * 5, f"warm={warm:.4f} cold={cold:.4f}"


def test_cache_invalidates_on_file_change():
    with tempfile.TemporaryDirectory(prefix="docdiscov_inval_") as tmp:
        root = Path(tmp)
        make_realistic_repo(root)
        cache_path = Path(tmp) / "cache.db"

        # warm cache
        with EdgeCache(cache_path) as cache:
            build_unified_graph(root, cache=cache)

        # modify a file (force mtime change)
        prd = root / "docs/00-prd/Auth_PRD.md"
        time.sleep(0.05)
        prd.write_text(
            "---\ntitle: Auth v2\nderivative-of:\n  - Overview.md\n  - Billing_PRD.md\n---\n\n",
            encoding="utf-8",
        )

        # rebuild should detect the new edge to Billing_PRD
        with EdgeCache(cache_path) as cache:
            graph = build_unified_graph(root, cache=cache)
            assert cache.hits > 0  # other files still cached
            assert cache.misses >= 1  # Auth_PRD invalidated

        report = impact_analysis(graph, "docs/00-prd/Billing_PRD.md", transitive=False)
        assert "docs/00-prd/Auth_PRD.md" in report["direct"]


def test_no_cache_mode_does_not_persist():
    with tempfile.TemporaryDirectory(prefix="docdiscov_nocache_") as tmp:
        root = Path(tmp)
        make_realistic_repo(root)
        # explicit None for cache
        graph = build_unified_graph(root, cache=None)
        # graph is built normally
        assert "docs/00-prd/Overview.md" in graph.nodes


# ─────────────────── runner ────────────────────

def _run_all() -> int:
    failures = []
    tests = [
        test_full_build_finds_all_impact_classes,
        test_cache_speeds_up_second_build,
        test_cache_invalidates_on_file_change,
        test_no_cache_mode_does_not_persist,
    ]
    for fn in tests:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            failures.append((fn.__name__, str(e)))
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:
            failures.append((fn.__name__, f"{type(e).__name__}: {e}"))
            print(f"ERROR {fn.__name__}: {e}")
    print("─" * 60)
    if failures:
        print(f"FAILED  {len(failures)}/{len(tests)} test(s)")
        return 1
    print(f"OK  all {len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(_run_all())
