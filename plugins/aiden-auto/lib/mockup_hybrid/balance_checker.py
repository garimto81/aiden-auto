"""
범용 레이아웃 밸런스 측정기

HTML 파일의 multi-column 레이아웃 밸런스를 Playwright DOM 측정으로 판정합니다.
export_utils.py의 Playwright 초기화를 공유합니다.

사용법:
    python balance_checker.py <html_path> [--config config.json] [--output result.json]
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

DEFAULT_THRESHOLDS = {
    "max_height_deviation_px": 50,
    "max_density_deviation_pct": 20,
    "whitespace_ratio_min": 25,
    "whitespace_ratio_max": 35,
    "max_scrollable_columns": 1,
}

JS_MEASURE_COLUMNS = """
() => {
    let containers = [...document.querySelectorAll(
        '[style*="display: flex"], [style*="display:flex"], ' +
        '[style*="display: grid"], [style*="display:grid"], ' +
        '.row, .flex, .grid, .q-page > div'
    )];
    if (containers.length === 0) {
        const body = document.body;
        const style = getComputedStyle(body);
        if (style.display === 'flex' || style.display === 'grid') {
            containers = [body];
        }
    }
    const results = [];
    for (const container of containers) {
        const children = Array.from(container.children).filter(
            c => getComputedStyle(c).display !== 'none'
        );
        if (children.length < 2) continue;

        const columns = children.map(child => {
            const rect = child.getBoundingClientRect();
            const controls = child.querySelectorAll(
                'input, select, textarea, button, [role="button"], ' +
                'a, label, .q-input, .q-select, .q-btn, .q-toggle'
            ).length;
            const totalArea = rect.width * rect.height;
            const textContent = child.innerText || '';
            const contentArea = textContent.length * 8;
            const whitespaceRatio = totalArea > 0
                ? ((totalArea - contentArea) / totalArea) * 100
                : 100;
            return {
                tag: child.tagName,
                height: Math.round(rect.height),
                width: Math.round(rect.width),
                controls: controls,
                whitespaceRatio: Math.round(whitespaceRatio),
                scrollable: child.scrollHeight > child.clientHeight + 5,
            };
        });
        results.push({ containerTag: container.tagName, columns });
    }
    return results;
}
"""


def measure_balance(html_path: Path, config: dict | None = None) -> dict:
    """HTML 파일의 multi-column 레이아웃 밸런스를 측정합니다."""
    if not _PLAYWRIGHT_AVAILABLE:
        return {
            "verdict": "SKIP",
            "reason": "Playwright not installed",
            "metrics": [],
        }

    thresholds = {**DEFAULT_THRESHOLDS, **(config or {})}
    file_url = html_path.resolve().as_uri()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(file_url, wait_until="networkidle")
            page.wait_for_timeout(500)
            raw = page.evaluate(JS_MEASURE_COLUMNS)
        finally:
            browser.close()

    if not raw:
        return {"verdict": "SKIP", "reason": "No multi-column layout detected", "metrics": []}

    failures = []
    all_metrics = []

    for group in raw:
        cols = group["columns"]
        if len(cols) < 2:
            continue

        heights = [c["height"] for c in cols]
        densities = [c["controls"] for c in cols]
        whitespaces = [c["whitespaceRatio"] for c in cols]
        scrollables = sum(1 for c in cols if c["scrollable"])

        height_dev = max(heights) - min(heights)
        avg_density = sum(densities) / len(densities) if densities else 0
        density_dev = (
            ((max(densities) - min(densities)) / avg_density * 100)
            if avg_density > 0
            else 0
        )
        avg_ws = sum(whitespaces) / len(whitespaces) if whitespaces else 0

        metric = {
            "container": group["containerTag"],
            "column_count": len(cols),
            "height_deviation_px": round(height_dev),
            "density_deviation_pct": round(density_dev, 1),
            "avg_whitespace_ratio": round(avg_ws, 1),
            "scrollable_columns": scrollables,
            "columns_detail": cols,
        }
        all_metrics.append(metric)

        if height_dev > thresholds["max_height_deviation_px"]:
            failures.append(f"Height deviation {height_dev}px > {thresholds['max_height_deviation_px']}px")
        if density_dev > thresholds["max_density_deviation_pct"]:
            failures.append(f"Density deviation {density_dev:.1f}% > {thresholds['max_density_deviation_pct']}%")
        if avg_ws < thresholds["whitespace_ratio_min"] or avg_ws > thresholds["whitespace_ratio_max"]:
            failures.append(f"Whitespace {avg_ws:.1f}% outside {thresholds['whitespace_ratio_min']}-{thresholds['whitespace_ratio_max']}%")
        if scrollables > thresholds["max_scrollable_columns"]:
            failures.append(f"Scrollable columns {scrollables} > {thresholds['max_scrollable_columns']}")

    verdict = "FAIL" if failures else "PASS"
    return {
        "verdict": verdict,
        "failures": failures,
        "metrics": all_metrics,
        "thresholds": thresholds,
        "file": str(html_path),
    }


def main():
    parser = argparse.ArgumentParser(description="HTML multi-column layout balance checker")
    parser.add_argument("html_path", type=Path, help="Path to HTML file")
    parser.add_argument("--config", type=Path, help="JSON config for thresholds", default=None)
    parser.add_argument("--output", type=Path, help="Output JSON path", default=None)
    args = parser.parse_args()

    if not args.html_path.exists():
        print(json.dumps({"verdict": "ERROR", "reason": f"File not found: {args.html_path}"}))
        sys.exit(1)

    config = None
    if args.config and args.config.exists():
        config = json.loads(args.config.read_text(encoding="utf-8"))

    result = measure_balance(args.html_path, config)
    output = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(f"Written to {args.output}")
    else:
        print(output)

    sys.exit(0 if result["verdict"] in ("PASS", "SKIP") else 1)


if __name__ == "__main__":
    main()
