"""
다이어그램 생성기

HTML 템플릿 → Playwright 캡처 → PNG 생성

Features:
- Jinja2 템플릿 렌더링
- Playwright 비동기 스크린샷 캡처
- 아키텍처, ERD, 플로우차트, UI 목업 지원
- 자동 높이 조정

Usage:
    from lib.google_docs.diagram_generator import DiagramGenerator

    generator = DiagramGenerator()

    # 아키텍처 다이어그램 생성
    png_path = generator.generate_architecture(
        data={'title': 'System Architecture', 'layers': [...]},
        output_path=Path('output/architecture.png')
    )
"""

import asyncio
import tempfile
from pathlib import Path
from typing import Any, Optional

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    Environment = None
    FileSystemLoader = None

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None


class DiagramGenerator:
    """다이어그램 생성 및 PNG 캡처"""

    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Args:
            templates_dir: HTML 템플릿 디렉토리 경로
        """
        self.templates_dir = templates_dir or Path(__file__).parent / "templates"

        if Environment is None or FileSystemLoader is None:
            raise ImportError("jinja2가 설치되어 있지 않습니다. pip install jinja2")

        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)), autoescape=True
        )

    async def _generate_diagram_async(
        self,
        template_name: str,
        data: dict[str, Any],
        output_path: Path,
        width: int = 540,
        height: Optional[int] = None,
    ) -> Path:
        """
        비동기로 다이어그램 이미지 생성

        Args:
            template_name: 템플릿 파일명 (e.g., 'architecture.html')
            data: 템플릿에 전달할 데이터
            output_path: 출력 PNG 경로
            width: 이미지 너비
            height: 이미지 높이 (None이면 자동)

        Returns:
            생성된 PNG 파일 경로
        """
        if async_playwright is None:
            raise ImportError(
                "playwright가 설치되어 있지 않습니다. pip install playwright && playwright install chromium"
            )

        # 1. 템플릿 렌더링
        template = self.env.get_template(template_name)
        html_content = template.render(**data)

        # 2. 임시 HTML 파일 저장
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as f:
            f.write(html_content)
            temp_html_path = Path(f.name)

        try:
            # 3. Playwright로 스크린샷
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(
                    viewport={"width": width, "height": height or 1080}
                )

                # 파일 URL로 이동
                await page.goto(f"file:///{temp_html_path.resolve()}")

                # 콘텐츠 로드 대기
                await page.wait_for_load_state("networkidle")

                # 콘텐츠 높이에 맞게 viewport 조정
                if height is None:
                    content_height = await page.evaluate("document.body.scrollHeight")
                    await page.set_viewport_size(
                        {"width": width, "height": content_height + 80}  # 여유 공간
                    )

                # 출력 디렉토리 생성
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # 스크린샷 캡처 (.container 영역만)
                container = await page.query_selector(".container")
                if container:
                    await container.screenshot(path=str(output_path), type="png")
                else:
                    await page.screenshot(
                        path=str(output_path), full_page=True, type="png"
                    )

                await browser.close()

        finally:
            # 4. 임시 파일 정리
            try:
                temp_html_path.unlink()
            except Exception:
                pass

        return output_path

    def generate_diagram(
        self,
        template_name: str,
        data: dict[str, Any],
        output_path: Path,
        width: int = 540,
        height: Optional[int] = None,
    ) -> Path:
        """
        동기 방식으로 다이어그램 생성 (내부적으로 asyncio 사용)

        Args:
            template_name: 템플릿 파일명
            data: 템플릿 데이터
            output_path: 출력 PNG 경로
            width: 이미지 너비
            height: 이미지 높이

        Returns:
            생성된 PNG 파일 경로
        """
        return asyncio.run(
            self._generate_diagram_async(
                template_name, data, output_path, width, height
            )
        )

    def generate_architecture(
        self,
        data: dict[str, Any],
        output_path: Path,
        width: int = 540,
    ) -> Path:
        """
        아키텍처 다이어그램 생성

        Args:
            data: {
                'title': str,
                'subtitle': str,
                'layers': [
                    {
                        'name': str,
                        'class': str (optional),
                        'components': [
                            {
                                'name': str,
                                'icon': str,
                                'bg_class': str,
                                'description': str,
                                'tags': [str]
                            }
                        ]
                    }
                ]
            }
            output_path: 출력 PNG 경로
            width: 이미지 너비

        Returns:
            생성된 PNG 파일 경로
        """
        return self.generate_diagram("architecture.html", data, output_path, width)

    def generate_erd(
        self,
        data: dict[str, Any],
        output_path: Path,
        width: int = 540,
    ) -> Path:
        """
        ERD 다이어그램 생성

        Args:
            data: {
                'title': str,
                'subtitle': str,
                'entities': [
                    {
                        'name': str,
                        'icon': str,
                        'color': str ('blue', 'green', 'purple', 'orange'),
                        'fields': [
                            {
                                'name': str,
                                'type': str,
                                'pk': bool,
                                'fk': bool,
                                'nullable': bool
                            }
                        ]
                    }
                ],
                'relations': [
                    {
                        'from': str,
                        'to': str,
                        'cardinality': str ('1:1', '1:N', 'N:M'),
                        'label': str
                    }
                ]
            }
            output_path: 출력 PNG 경로
            width: 이미지 너비

        Returns:
            생성된 PNG 파일 경로
        """
        return self.generate_diagram("erd.html", data, output_path, width)

    def generate_flowchart(
        self,
        data: dict[str, Any],
        output_path: Path,
        width: int = 540,
    ) -> Path:
        """
        플로우차트 생성

        Args:
            data: {
                'title': str,
                'subtitle': str,
                'steps': [
                    {
                        'title': str,
                        'description': str,
                        'icon': str,
                        'type': str ('start', 'end', 'action', 'decision'),
                        'branches': [
                            {'label': str, 'action': str}
                        ],
                        'note': str
                    }
                ]
            }
            output_path: 출력 PNG 경로
            width: 이미지 너비

        Returns:
            생성된 PNG 파일 경로
        """
        return self.generate_diagram("flowchart.html", data, output_path, width)

    def generate_ui_mockup(
        self,
        data: dict[str, Any],
        output_path: Path,
        width: int = 540,
    ) -> Path:
        """
        UI 목업 생성

        Args:
            data: {
                'title': str,
                'subtitle': str,
                'url': str,
                'layout': str ('sidebar', None),
                'app_name': str,
                'menu_items': [
                    {'label': str, 'icon': str, 'active': bool}
                ],
                'content': str (HTML 내용)
            }
            output_path: 출력 PNG 경로
            width: 이미지 너비

        Returns:
            생성된 PNG 파일 경로
        """
        return self.generate_diagram("ui-mockup.html", data, output_path, width)

    def render_html(
        self,
        template_name: str,
        data: dict[str, Any],
    ) -> str:
        """
        HTML만 렌더링 (PNG 캡처 없이)

        Args:
            template_name: 템플릿 파일명
            data: 템플릿 데이터

        Returns:
            렌더링된 HTML 문자열
        """
        template = self.env.get_template(template_name)
        return template.render(**data)

    def save_html(
        self,
        template_name: str,
        data: dict[str, Any],
        output_path: Path,
    ) -> Path:
        """
        HTML 파일로 저장 (디버깅/미리보기용)

        Args:
            template_name: 템플릿 파일명
            data: 템플릿 데이터
            output_path: 출력 HTML 경로

        Returns:
            저장된 HTML 파일 경로
        """
        html_content = self.render_html(template_name, data)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding="utf-8")
        return output_path


# 편의 함수
def create_generator(templates_dir: Optional[Path] = None) -> DiagramGenerator:
    """DiagramGenerator 인스턴스 생성"""
    return DiagramGenerator(templates_dir)
