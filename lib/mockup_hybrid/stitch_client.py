"""
Google Stitch API 클라이언트

Google Stitch는 AI 기반 UI 디자인 생성 도구입니다.
프롬프트를 기반으로 고품질 UI 목업을 생성합니다.

사용법:
    from lib.mockup_hybrid.stitch_client import StitchClient

    client = StitchClient()
    if client.is_available():
        result = client.generate_ui("로그인 화면", "사용자 인증을 위한 깔끔한 로그인 폼")
        print(result.html_content)
"""

import os
import json
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)


@dataclass
class StitchResponse:
    """Stitch API 응답"""
    success: bool
    html_content: Optional[str] = None
    image_url: Optional[str] = None
    error_message: Optional[str] = None
    rate_limited: bool = False


class StitchClient:
    """Google Stitch API 클라이언트"""

    DEFAULT_BASE_URL = "https://stitch.withgoogle.com/api/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        StitchClient 초기화

        Args:
            api_key: Stitch API 키 (없으면 환경변수에서 로드)
            base_url: API 기본 URL (없으면 기본값 사용)
        """
        self.api_key = api_key or os.getenv("STITCH_API_KEY")
        self.base_url = base_url or os.getenv(
            "STITCH_API_BASE_URL", self.DEFAULT_BASE_URL
        )
        self._monthly_usage: int = 0
        self._monthly_limit: int = 350  # 무료 한도

    def is_available(self) -> bool:
        """
        Stitch API 사용 가능 여부 확인

        Returns:
            API 키가 유효하고 사용 가능하면 True
        """
        if not self.api_key:
            logger.debug("Stitch API 키가 설정되지 않음")
            return False

        # 빈 문자열 체크
        if not self.api_key.strip():
            logger.debug("Stitch API 키가 비어 있음")
            return False

        return True

    def is_rate_limited(self) -> bool:
        """
        Rate limit 초과 여부 확인

        Returns:
            월간 한도 초과 시 True
        """
        return self._monthly_usage >= self._monthly_limit

    def generate_ui(
        self,
        screen_name: str,
        description: str,
        style: str = "modern",
        color_scheme: Optional[str] = None,
    ) -> StitchResponse:
        """
        UI 목업 생성

        Args:
            screen_name: 화면 이름
            description: 화면 설명
            style: 디자인 스타일 (modern, minimal, corporate)
            color_scheme: 색상 스키마 (optional)

        Returns:
            StitchResponse 객체
        """
        if not self.is_available():
            return StitchResponse(
                success=False,
                error_message="Stitch API 키가 설정되지 않았습니다.",
            )

        if self.is_rate_limited():
            return StitchResponse(
                success=False,
                error_message="월간 사용 한도를 초과했습니다.",
                rate_limited=True,
            )

        try:
            payload = {
                "prompt": f"{screen_name}: {description}",
                "style": style,
                "output_format": "html",
            }

            if color_scheme:
                payload["color_scheme"] = color_scheme

            # API 호출
            response = self._make_request("/generate", payload)

            if response.get("success"):
                self._monthly_usage += 1
                return StitchResponse(
                    success=True,
                    html_content=response.get("html"),
                    image_url=response.get("image_url"),
                )
            else:
                return StitchResponse(
                    success=False,
                    error_message=response.get("error", "알 수 없는 오류"),
                )

        except HTTPError as e:
            if e.code == 429:
                return StitchResponse(
                    success=False,
                    error_message="Rate limit 초과",
                    rate_limited=True,
                )
            logger.error(f"Stitch API HTTP 오류: {e.code} - {e.reason}")
            return StitchResponse(
                success=False,
                error_message=f"HTTP 오류: {e.code}",
            )

        except URLError as e:
            logger.error(f"Stitch API 연결 오류: {e.reason}")
            return StitchResponse(
                success=False,
                error_message=f"연결 오류: {e.reason}",
            )

        except Exception as e:
            logger.error(f"Stitch API 예외: {e}")
            return StitchResponse(
                success=False,
                error_message=str(e),
            )

    def _make_request(self, endpoint: str, payload: dict) -> dict:
        """
        API 요청 실행

        Args:
            endpoint: API 엔드포인트
            payload: 요청 본문

        Returns:
            응답 JSON
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = json.dumps(payload).encode("utf-8")
        request = Request(url, data=data, headers=headers, method="POST")

        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_usage_stats(self) -> dict:
        """
        사용량 통계 반환

        Returns:
            사용량 정보 딕셔너리
        """
        return {
            "monthly_usage": self._monthly_usage,
            "monthly_limit": self._monthly_limit,
            "remaining": self._monthly_limit - self._monthly_usage,
            "available": self.is_available(),
            "rate_limited": self.is_rate_limited(),
        }


# 싱글톤 인스턴스 (선택적 사용)
_default_client: Optional[StitchClient] = None


def get_stitch_client() -> StitchClient:
    """
    기본 Stitch 클라이언트 인스턴스 반환

    Returns:
        StitchClient 인스턴스
    """
    global _default_client
    if _default_client is None:
        _default_client = StitchClient()
    return _default_client
