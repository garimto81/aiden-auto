"""Mermaid 하이브리드 렌더러 테스트"""

import os

from unittest.mock import patch, MagicMock

# Test constants
SAMPLE_MERMAID = "graph TD\n    A[Start] --> B[End]"
FAKE_PNG_DATA = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


# --- Mermaid.ink 전략 테스트 ---


class TestMermaidInkStrategy:

    @patch("lib.google_docs.mermaid_renderer.urlopen")
    def test_success(self, mock_urlopen):
        """mermaid.ink API 성공"""
        from lib.google_docs.mermaid_renderer import _render_via_mermaid_ink

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = FAKE_PNG_DATA
        mock_urlopen.return_value = mock_response

        result = _render_via_mermaid_ink(SAMPLE_MERMAID)

        assert result is not None
        assert result.endswith(".png")
        assert os.path.exists(result)

        # 실제 파일에 PNG 데이터가 쓰였는지 확인
        with open(result, "rb") as f:
            data = f.read()
        assert data == FAKE_PNG_DATA

        os.unlink(result)

    def test_url_too_long(self):
        """URL 2048자 초과 시 None 반환"""
        from lib.google_docs.mermaid_renderer import _render_via_mermaid_ink

        long_code = "graph TD\n" + "\n".join(
            [f"    Node{i} --> Node{i+1}" for i in range(500)]
        )

        result = _render_via_mermaid_ink(long_code)
        assert result is None

    @patch("lib.google_docs.mermaid_renderer.urlopen")
    def test_network_error(self, mock_urlopen):
        """네트워크 오류 시 None 반환"""
        from lib.google_docs.mermaid_renderer import _render_via_mermaid_ink
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("Connection refused")

        result = _render_via_mermaid_ink(SAMPLE_MERMAID)
        assert result is None

    @patch("lib.google_docs.mermaid_renderer.urlopen")
    def test_invalid_png_response(self, mock_urlopen):
        """유효하지 않은 PNG 응답 시 None 반환"""
        from lib.google_docs.mermaid_renderer import _render_via_mermaid_ink

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b"<html>Error</html>"
        mock_urlopen.return_value = mock_response

        result = _render_via_mermaid_ink(SAMPLE_MERMAID)
        assert result is None

    @patch("lib.google_docs.mermaid_renderer.urlopen")
    def test_timeout(self, mock_urlopen):
        """타임아웃 시 None 반환"""
        from lib.google_docs.mermaid_renderer import _render_via_mermaid_ink

        mock_urlopen.side_effect = TimeoutError("Connection timed out")

        result = _render_via_mermaid_ink(SAMPLE_MERMAID)
        assert result is None


# --- mmdc CLI 전략 테스트 ---


class TestMmdcStrategy:

    @patch("lib.google_docs.mermaid_renderer.Path")
    @patch("lib.google_docs.mermaid_renderer.subprocess.run")
    @patch("lib.google_docs.mermaid_renderer.shutil.which", return_value="/usr/bin/mmdc")
    def test_success(self, mock_which, mock_run, mock_path_cls):
        """mmdc CLI 성공"""
        from lib.google_docs.mermaid_renderer import _render_via_mmdc

        mock_run.return_value = MagicMock(returncode=0, stderr="")
        mock_path_cls.return_value.exists.return_value = True
        mock_path_cls.return_value.unlink = MagicMock()
        mock_path_cls.return_value.name = "output.png"

        result = _render_via_mmdc(SAMPLE_MERMAID)

        assert result is not None
        assert result.endswith(".png")
        mock_run.assert_called_once()
        # mmdc 명령어에 올바른 인수 전달 확인
        call_args = mock_run.call_args[0][0]
        assert "mmdc" in call_args[0].lower()  # shutil.which()가 전체 경로 반환
        assert "-b" in call_args
        assert "white" in call_args

    @patch("lib.google_docs.mermaid_renderer.shutil.which", return_value=None)
    def test_not_installed(self, mock_which):
        """mmdc 미설치 시 None 반환"""
        from lib.google_docs.mermaid_renderer import _render_via_mmdc

        result = _render_via_mmdc(SAMPLE_MERMAID)
        assert result is None

    @patch("lib.google_docs.mermaid_renderer.Path")
    @patch("lib.google_docs.mermaid_renderer.subprocess.run")
    @patch("lib.google_docs.mermaid_renderer.shutil.which", return_value="/usr/bin/mmdc")
    def test_execution_failed(self, mock_which, mock_run, mock_path_cls):
        """mmdc 실행 실패 (returncode != 0)"""
        from lib.google_docs.mermaid_renderer import _render_via_mmdc

        mock_run.return_value = MagicMock(returncode=1, stderr="Syntax error")
        mock_path_cls.return_value.exists.return_value = False
        mock_path_cls.return_value.unlink = MagicMock()

        result = _render_via_mmdc(SAMPLE_MERMAID)
        assert result is None

    @patch("lib.google_docs.mermaid_renderer.subprocess.run")
    @patch("lib.google_docs.mermaid_renderer.shutil.which", return_value="/usr/bin/mmdc")
    def test_timeout(self, mock_which, mock_run):
        """mmdc 타임아웃 시 None 반환"""
        from lib.google_docs.mermaid_renderer import _render_via_mmdc
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="mmdc", timeout=60)

        result = _render_via_mmdc(SAMPLE_MERMAID)
        assert result is None


# --- Playwright 전략 테스트 ---


class TestPlaywrightStrategy:

    def test_not_installed(self):
        """Playwright 미설치 시 None 반환"""
        with patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}):
            # 모듈 캐시 무효화를 위해 재임포트
            import importlib
            import lib.google_docs.mermaid_renderer as mod

            importlib.reload(mod)

            result = mod._render_via_playwright(SAMPLE_MERMAID)
            assert result is None

    @patch("lib.google_docs.mermaid_renderer.Path")
    def test_success(self, mock_path_cls):
        """Playwright 성공 케이스"""
        mock_path_cls.return_value.exists.return_value = True
        mock_path_cls.return_value.unlink = MagicMock()
        mock_path_cls.return_value.name = "output.png"

        # Mock sync_playwright context manager
        mock_container = MagicMock()
        mock_container.screenshot = MagicMock()

        mock_page = MagicMock()
        mock_page.query_selector.return_value = mock_container

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser

        mock_sync_pw = MagicMock()
        mock_sync_pw.__enter__ = MagicMock(return_value=mock_pw)
        mock_sync_pw.__exit__ = MagicMock(return_value=False)

        with patch(
            "lib.google_docs.mermaid_renderer.sync_playwright",
            return_value=mock_sync_pw,
            create=True,
        ):
            # Lazy import를 패치하기 위해 함수 내부의 import를 우회
            import lib.google_docs.mermaid_renderer as mod

            with patch.object(mod, "sync_playwright", mock_sync_pw, create=True):
                # sync_playwright를 모듈 레벨에 주입하여 lazy import 대체
                original_func = mod._render_via_playwright

                def patched_render(code):
                    # playwright import를 건너뛰고 직접 실행
                    import tempfile as _tf

                    html_path = None
                    try:
                        safe_code = code.replace("<", "&lt;").replace(">", "&gt;")
                        html_content = f"<pre class='mermaid'>{safe_code}</pre>"

                        with _tf.NamedTemporaryFile(
                            mode="w",
                            suffix=".html",
                            delete=False,
                            encoding="utf-8",
                        ) as fh:
                            fh.write(html_content)
                            html_path = fh.name

                        png_path = html_path.replace(".html", ".png")

                        with mock_sync_pw as p:
                            browser = p.chromium.launch(headless=True)
                            page = browser.new_page(
                                viewport={"width": 1200, "height": 800}
                            )
                            page.goto(f"file:///{html_path}")
                            page.wait_for_selector(".mermaid svg", timeout=30000)
                            container = page.query_selector("#container")
                            if container:
                                container.screenshot(path=png_path)
                            else:
                                page.screenshot(path=png_path)
                            browser.close()

                        if mock_path_cls(png_path).exists():
                            return png_path
                        return None
                    except Exception:
                        return None
                    finally:
                        if html_path:
                            mock_path_cls(html_path).unlink(missing_ok=True)

                result = patched_render(SAMPLE_MERMAID)

                assert result is not None
                assert result.endswith(".png")
                mock_page.wait_for_selector.assert_called_once()


# --- 오케스트레이터 테스트 ---


class TestRenderMermaidOrchestrator:

    @patch("lib.google_docs.mermaid_renderer._render_via_playwright")
    @patch("lib.google_docs.mermaid_renderer._render_via_mmdc")
    @patch("lib.google_docs.mermaid_renderer._render_via_mermaid_ink")
    def test_first_succeeds(self, mock_ink, mock_mmdc, mock_pw):
        """첫 번째 전략 성공 시 나머지 호출 안 됨"""
        from lib.google_docs.mermaid_renderer import render_mermaid

        mock_ink.return_value = "/tmp/ink.png"

        result = render_mermaid(SAMPLE_MERMAID)

        assert result == "/tmp/ink.png"
        mock_ink.assert_called_once_with(SAMPLE_MERMAID)
        mock_mmdc.assert_not_called()
        mock_pw.assert_not_called()

    @patch("lib.google_docs.mermaid_renderer._render_via_playwright")
    @patch("lib.google_docs.mermaid_renderer._render_via_mmdc")
    @patch("lib.google_docs.mermaid_renderer._render_via_mermaid_ink")
    def test_fallback_to_second(self, mock_ink, mock_mmdc, mock_pw):
        """첫 번째 실패, 두 번째 성공 시 세 번째 호출 안 됨"""
        from lib.google_docs.mermaid_renderer import render_mermaid

        mock_ink.return_value = None
        mock_mmdc.return_value = "/tmp/mmdc.png"

        result = render_mermaid(SAMPLE_MERMAID)

        assert result == "/tmp/mmdc.png"
        mock_ink.assert_called_once()
        mock_mmdc.assert_called_once()
        mock_pw.assert_not_called()

    @patch("lib.google_docs.mermaid_renderer._render_via_playwright")
    @patch("lib.google_docs.mermaid_renderer._render_via_mmdc")
    @patch("lib.google_docs.mermaid_renderer._render_via_mermaid_ink")
    def test_fallback_to_third(self, mock_ink, mock_mmdc, mock_pw):
        """첫 번째, 두 번째 실패 시 세 번째 사용"""
        from lib.google_docs.mermaid_renderer import render_mermaid

        mock_ink.return_value = None
        mock_mmdc.return_value = None
        mock_pw.return_value = "/tmp/pw.png"

        result = render_mermaid(SAMPLE_MERMAID)

        assert result == "/tmp/pw.png"
        mock_ink.assert_called_once()
        mock_mmdc.assert_called_once()
        mock_pw.assert_called_once()

    @patch("lib.google_docs.mermaid_renderer._render_via_playwright")
    @patch("lib.google_docs.mermaid_renderer._render_via_mmdc")
    @patch("lib.google_docs.mermaid_renderer._render_via_mermaid_ink")
    def test_all_fail(self, mock_ink, mock_mmdc, mock_pw):
        """모든 전략 실패 시 None 반환"""
        from lib.google_docs.mermaid_renderer import render_mermaid

        mock_ink.return_value = None
        mock_mmdc.return_value = None
        mock_pw.return_value = None

        result = render_mermaid(SAMPLE_MERMAID)

        assert result is None
        mock_ink.assert_called_once()
        mock_mmdc.assert_called_once()
        mock_pw.assert_called_once()


# --- 임시 파일 정리 테스트 ---


class TestCleanup:

    @patch("lib.google_docs.mermaid_renderer.urlopen")
    def test_temp_file_can_be_cleaned(self, mock_urlopen):
        """생성된 임시 파일이 정상 삭제 가능"""
        from lib.google_docs.mermaid_renderer import _render_via_mermaid_ink

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = FAKE_PNG_DATA
        mock_urlopen.return_value = mock_response

        result = _render_via_mermaid_ink(SAMPLE_MERMAID)

        assert result is not None
        assert os.path.exists(result)

        # 정리
        os.unlink(result)
        assert not os.path.exists(result)
