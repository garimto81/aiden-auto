"""
Google Drive 프로젝트 레지스트리

YAML 설정 파일에서 프로젝트별 Drive 폴더 ID를 관리하고 자동 해석합니다.
"""

import warnings
from pathlib import Path
from fnmatch import fnmatch
from typing import Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from .auth import _get_project_root


class ProjectRegistry:
    """프로젝트별 Drive 폴더 매핑 레지스트리 (Singleton)"""

    _instance: Optional['ProjectRegistry'] = None

    def __new__(cls, config_path: Optional[Path] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: Optional[Path] = None):
        """
        YAML 설정 파일에서 프로젝트 레지스트리 로드

        Args:
            config_path: 설정 파일 경로 (기본값: <project_root>/config/drive_projects.yaml)
        """
        if self._initialized:
            return

        if config_path is None:
            project_root = _get_project_root()
            config_path = project_root / "config" / "drive_projects.yaml"

        self.config_path = Path(config_path)
        self._config = self._load_config()
        self._initialized = True

    @classmethod
    def get_instance(cls, config_path: Optional[Path] = None) -> 'ProjectRegistry':
        """
        Singleton 인스턴스 반환 (팩토리 메서드)

        Args:
            config_path: 설정 파일 경로 (첫 호출 시만 사용)

        Returns:
            ProjectRegistry 인스턴스
        """
        if cls._instance is None:
            cls._instance = cls(config_path)
        return cls._instance

    @classmethod
    def reset(cls):
        """Singleton 인스턴스 초기화 (테스트용)"""
        cls._instance = None

    def _load_config(self) -> dict:
        """YAML 설정 파일 로드"""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"프로젝트 레지스트리 설정 파일을 찾을 수 없습니다: {self.config_path}"
            )

        if not HAS_YAML:
            raise ImportError(
                "PyYAML이 설치되지 않았습니다. 'pip install pyyaml'을 실행하세요."
            )

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 파싱 오류: {self.config_path} - {e}")
        except Exception as e:
            raise RuntimeError(f"설정 파일 읽기 실패: {self.config_path} - {e}")

        if not config or 'projects' not in config:
            raise ValueError(f"잘못된 설정 파일 형식: {self.config_path}")

        return config

    def resolve_project(self, hint: Optional[str] = None) -> str:
        """
        프로젝트 이름 해석

        우선순위:
        1. hint가 제공된 경우: 프로젝트 이름/별칭 매칭 (대소문자 무시)
        2. hint가 없는 경우: CWD 기반 자동 감지 (cwd_patterns)
        3. 매칭 실패: default_project 반환

        Args:
            hint: 프로젝트 이름 힌트 (별칭 포함)

        Returns:
            해석된 프로젝트 이름
        """
        projects = self._config.get('projects', {})

        # 1. hint 기반 매칭
        if hint:
            hint_lower = hint.lower()

            # 정확한 이름 매칭
            for project_name in projects.keys():
                if project_name.lower() == hint_lower:
                    return project_name

            # 별칭 매칭
            for project_name, project_config in projects.items():
                aliases = project_config.get('aliases', [])
                if any(alias.lower() == hint_lower for alias in aliases):
                    return project_name

        # 2. CWD 기반 자동 감지 (Windows 경로 정규화)
        cwd = Path.cwd().as_posix()
        for project_name, project_config in projects.items():
            patterns = project_config.get('cwd_patterns', [])
            for pattern in patterns:
                if fnmatch(cwd, pattern) or fnmatch(cwd.lower(), pattern.lower()):
                    return project_name

        # 3. 기본 프로젝트 반환 (빈 dict 방어)
        default_project = self._config.get('default_project')
        if default_project:
            return default_project

        # default_project가 없으면 첫 번째 프로젝트 반환
        if projects:
            return next(iter(projects.keys()))

        raise ValueError("설정 파일에 프로젝트가 정의되지 않았습니다")

    def get_folder_id(self, project: Optional[str] = None, subfolder: Optional[str] = None) -> str:
        """
        프로젝트 폴더 ID 반환

        Args:
            project: 프로젝트 이름 (None이면 자동 해석)
            subfolder: 하위 폴더 이름 ("documents", "images" 등)

        Returns:
            Drive 폴더 ID

        Raises:
            KeyError: 프로젝트 또는 하위 폴더를 찾을 수 없는 경우
        """
        if project is None:
            project = self.resolve_project()

        projects = self._config.get('projects', {})
        if project not in projects:
            raise KeyError(f"프로젝트를 찾을 수 없습니다: {project}")

        project_config = projects[project]

        if subfolder is None:
            return project_config['folder_id']

        subfolders = project_config.get('subfolders', {})
        if subfolder not in subfolders:
            raise KeyError(
                f"프로젝트 '{project}'에 하위 폴더 '{subfolder}'가 없습니다. "
                f"사용 가능한 하위 폴더: {list(subfolders.keys())}"
            )

        return subfolders[subfolder]

    def get_project_config(self, project: Optional[str] = None) -> dict:
        """
        프로젝트 전체 설정 반환

        Args:
            project: 프로젝트 이름 (None이면 자동 해석)

        Returns:
            프로젝트 설정 딕셔너리
        """
        if project is None:
            project = self.resolve_project()

        projects = self._config.get('projects', {})
        if project not in projects:
            raise KeyError(f"프로젝트를 찾을 수 없습니다: {project}")

        return projects[project]

    def list_projects(self) -> list[str]:
        """
        모든 프로젝트 이름 목록 반환

        Returns:
            프로젝트 이름 리스트
        """
        return list(self._config.get('projects', {}).keys())

    def get_special_folder(self, name: str, subfolder: Optional[str] = None) -> str:
        """
        특수 폴더 ID 반환 (_개인 등)

        Args:
            name: 특수 폴더 이름 (예: "_개인")
            subfolder: 하위 폴더 이름 (예: "증명서")

        Returns:
            Drive 폴더 ID

        Raises:
            KeyError: 특수 폴더를 찾을 수 없는 경우
        """
        special = self._config.get('special_folders', {})
        if name not in special:
            raise KeyError(f"특수 폴더를 찾을 수 없습니다: {name}")

        folder_config = special[name]

        if subfolder is None:
            return folder_config['folder_id']

        subfolders = folder_config.get('subfolders', {})
        if subfolder not in subfolders:
            raise KeyError(
                f"특수 폴더 '{name}'에 하위 폴더 '{subfolder}'가 없습니다. "
                f"사용 가능한 하위 폴더: {list(subfolders.keys())}"
            )

        return subfolders[subfolder]

    def get_legacy_folder_id(self) -> str:
        """
        레거시 Google AI Studio 폴더 ID 반환 (하위 호환성)

        .. deprecated::
            프로젝트 기반 구조로 전환 권장. get_folder_id() 사용을 권장합니다.

        Returns:
            레거시 폴더 ID

        Raises:
            KeyError: 레거시 설정이 없는 경우
        """
        warnings.warn(
            "get_legacy_folder_id()는 deprecated입니다. "
            "get_folder_id()를 사용하세요.",
            DeprecationWarning,
            stacklevel=2
        )

        legacy = self._config.get('legacy', {})
        if 'google_ai_studio' not in legacy:
            raise KeyError("레거시 Google AI Studio 폴더 설정이 없습니다")

        return legacy['google_ai_studio']['folder_id']


# Singleton 인스턴스
_registry: Optional[ProjectRegistry] = None


def get_project_folder_id(project: Optional[str] = None, subfolder: Optional[str] = None) -> str:
    """
    프로젝트 폴더 ID 반환 (편의 함수)

    Args:
        project: 프로젝트 이름 (None이면 자동 해석)
        subfolder: 하위 폴더 이름

    Returns:
        Drive 폴더 ID
    """
    registry = ProjectRegistry.get_instance()
    return registry.get_folder_id(project, subfolder)


def get_default_folder_id(project: Optional[str] = None) -> str:
    """
    프로젝트 루트 폴더 ID 반환 (하위 호환성 함수)

    Args:
        project: 프로젝트 이름 (None이면 자동 해석)

    Returns:
        프로젝트 루트 폴더 ID
    """
    return get_project_folder_id(project=project, subfolder=None)
