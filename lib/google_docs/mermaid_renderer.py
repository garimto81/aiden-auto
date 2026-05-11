"""
Mermaid 다이어그램 하이브리드 렌더러

렌더링 우선순위:
1. Mermaid.ink API (의존성 없음, HTTP 요청만)
2. mmdc CLI (Node.js mermaid-cli 설치 필요)
3. Playwright 브라우저 렌더링

모든 전략은 로컬 PNG 파일 경로를 반환합니다.
"""

import base64
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError


def render_mermaid(code: str) -> str | None:
    """
    하이브리드 Mermaid 렌더링 (3단계 폴백)

    Args:
        code: Mermaid 다이어그램 코드

    Returns:
        str | None: 생성된 PNG 파일 절대 경로, 모든 전략 실패 시 None
    """
    # Strategy 1: Mermaid.ink API
    result = _render_via_mermaid_ink(code)
    if result:
        return result

    # Strategy 2: mmdc CLI
    result = _render_via_mmdc(code)
    if result:
        return result

    # Strategy 3: Playwright
    result = _render_via_playwright(code)
    if result:
        return result

    print("     [WARN] Mermaid 렌더링 실패 (모든 전략 실패) - 코드 블록으로 표시")
    return None


def _render_via_mermaid_ink(code: str) -> str | None:
    """
    Mermaid.ink API를 사용하여 PNG 다운로드

    Mermaid 코드를 Base64 URL-safe 인코딩하여 mermaid.ink 서비스에서 PNG를 가져옵니다.
    외부 의존성 없이 stdlib만 사용합니다.

    Args:
        code: Mermaid 다이어그램 코드

    Returns:
        str | None: PNG 파일 경로, 실패 시 None
    """
    try:
        encoded = base64.urlsafe_b64encode(code.encode("utf-8")).decode("ascii")
        url = f"https://mermaid.ink/img/{encoded}?type=png&bgColor=white"

        # URL 길이 제한 검사 (Google Docs API URI 제한: 2KB)
        if len(url) > 2048:
            print("     [INFO] Mermaid.ink URL 길이 초과 (>2KB) - 다음 전략 시도")
            return None

        req = Request(url, headers={"User-Agent": "GoogleDocs-MermaidRenderer/1.0"})
        response = urlopen(req, timeout=30)

        if response.status == 200:
            png_data = response.read()

            # PNG 헤더 검증
            if not png_data.startswith(b"\x89PNG"):
                print("     [INFO] Mermaid.ink 응답이 유효한 PNG가 아님 - 다음 전략 시도")
                return None

            # 크기 제한 (10MB)
            if len(png_data) > 10 * 1024 * 1024:
                print("     [INFO] Mermaid.ink PNG 크기 초과 (>10MB) - 다음 전략 시도")
                return None

            with tempfile.NamedTemporaryFile(
                suffix=".png", delete=False, prefix="mermaid_ink_"
            ) as f:
                f.write(png_data)
                png_path = f.name

            print(f"     Mermaid 렌더링됨 (mermaid.ink): {Path(png_path).name}")
            return png_path

        print(f"     [INFO] Mermaid.ink HTTP {response.status} - 다음 전략 시도")
        return None

    except (URLError, TimeoutError) as e:
        print(f"     [INFO] Mermaid.ink 접속 실패: {e} - 다음 전략 시도")
        return None
    except Exception as e:
        print(f"     [INFO] Mermaid.ink 렌더링 실패: {e} - 다음 전략 시도")
        return None


def _render_via_mmdc(code: str) -> str | None:
    """
    mmdc CLI (mermaid-cli)를 사용하여 로컬 렌더링

    Node.js + @mermaid-js/mermaid-cli가 설치되어 있어야 합니다.
    npx mmdc 또는 전역 설치된 mmdc를 사용합니다.

    Args:
        code: Mermaid 다이어그램 코드

    Returns:
        str | None: PNG 파일 경로, 실패 시 None
    """
    mmd_path = None
    png_path = None
    cfg_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".mmd", delete=False, encoding="utf-8", prefix="mermaid_mmdc_"
        ) as f:
            f.write(code)
            mmd_path = f.name

        png_path = mmd_path.replace(".mmd", ".png")
        cfg_path = mmd_path.replace(".mmd", ".json")
        with open(cfg_path, "w", encoding="utf-8") as cf:
            json.dump({"theme": "default", "fontSize": 18}, cf)

        # shutil.which()로 실행 파일 경로를 직접 해결 (shell=True 회피)
        mmdc_path = shutil.which("mmdc")
        if not mmdc_path:
            print("     [INFO] mmdc 미설치 - 다음 전략 시도")
            return None

        result = subprocess.run(
            [mmdc_path, "-i", mmd_path, "-o", png_path, "-b", "white", "-s", "2", "-c", cfg_path],
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
            errors="replace",
        )

        if result.returncode == 0 and Path(png_path).exists():
            print(f"     Mermaid 렌더링됨 (mmdc): {Path(png_path).name}")
            return png_path

        stderr_msg = (result.stderr or "")[:200]
        print(f"     [INFO] mmdc 렌더링 실패: {stderr_msg} - 다음 전략 시도")
        Path(png_path).unlink(missing_ok=True)
        return None

    except FileNotFoundError:
        print("     [INFO] mmdc 미설치 - 다음 전략 시도")
        return None
    except subprocess.TimeoutExpired:
        print("     [INFO] mmdc 타임아웃 (60초) - 다음 전략 시도")
        if png_path:
            Path(png_path).unlink(missing_ok=True)
        return None
    except Exception as e:
        print(f"     [INFO] mmdc 렌더링 실패: {e} - 다음 전략 시도")
        if png_path:
            Path(png_path).unlink(missing_ok=True)
        return None
    finally:
        # .mmd/.json 임시 파일 정리 (PNG는 호출자가 관리)
        if mmd_path:
            Path(mmd_path).unlink(missing_ok=True)
        if cfg_path:
            Path(cfg_path).unlink(missing_ok=True)


def _render_via_playwright(code: str) -> str | None:
    """
    Playwright 헤드리스 브라우저로 Mermaid 렌더링

    Mermaid.js CDN을 로드하여 브라우저에서 직접 렌더링 후 스크린샷 캡처.

    Args:
        code: Mermaid 다이어그램 코드

    Returns:
        str | None: PNG 파일 경로, 실패 시 None
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("     [INFO] Playwright 미설치 - 다음 전략 시도")
        return None

    html_path = None

    try:
        # Mermaid 코드는 <pre> 내부 텍스트로 처리되어 XSS 위험 없음
        # HTML 이스케이프 시 --> 등 Mermaid 문법이 파괴되므로 원본 그대로 사용
        # (로컬 임시 파일 + 헤드리스 브라우저이므로 보안 위험 없음)
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
    <style>
        body {{ background: white; margin: 0; padding: 20px; }}
        #container {{ display: inline-block; }}
    </style>
</head>
<body>
    <div id="container">
        <pre class="mermaid">{code}</pre>
    </div>
    <script>
        mermaid.initialize({{ startOnLoad: true, theme: 'default', fontSize: 18 }});
    </script>
</body>
</html>"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8", prefix="mermaid_pw_"
        ) as f:
            f.write(html_content)
            html_path = f.name

        png_path = html_path.replace(".html", ".png")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 4000})

            # file:// 프로토콜로 로컬 HTML 로드
            page.goto(f"file:///{html_path.replace(chr(92), '/')}")

            # Mermaid SVG 렌더링 완료 대기
            page.wait_for_selector(".mermaid svg", timeout=30000)

            # 렌더링된 컨테이너 스크린샷
            container = page.query_selector("#container")
            if container:
                container.screenshot(path=png_path)
            else:
                page.screenshot(path=png_path)

            browser.close()

        if Path(png_path).exists():
            print(f"     Mermaid 렌더링됨 (Playwright): {Path(png_path).name}")
            return png_path

        return None

    except Exception as e:
        print(f"     [INFO] Playwright 렌더링 실패: {e} - 다음 전략 시도")
        return None
    finally:
        # HTML 임시 파일 정리
        if html_path:
            Path(html_path).unlink(missing_ok=True)
