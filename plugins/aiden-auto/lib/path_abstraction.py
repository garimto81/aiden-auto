"""
path_abstraction.py — Windows/POSIX 경로 추상화

aiden-auto 슈퍼 플러그인의 모든 경로 처리는 이 레이어를 통과한다.
Windows의 backslash와 POSIX의 forward slash를 통일 + junction/symlink 차이 흡수.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

OSType = Literal["windows", "darwin", "linux"]


@dataclass
class Runtime:
    """현재 런타임 환경 스냅샷"""
    os: OSType
    shell: str
    path_separator: str
    null_device: str
    python_executable: str
    plugin_root: str
    project_dir: str
    profile: str
    eco_mode: str

    def to_dict(self) -> dict:
        return asdict(self)


def detect_os() -> OSType:
    s = sys.platform
    if s.startswith("win"):
        return "windows"
    if s == "darwin":
        return "darwin"
    return "linux"


def normalize_path(p: str | Path) -> str:
    """경로를 OS-agnostic하게 정규화 (내부 처리는 항상 forward slash)"""
    return str(Path(p)).replace("\\", "/")


def to_native(p: str | Path) -> str:
    """OS native path로 변환 (Windows는 backslash)"""
    return str(Path(p))


def detect_project_profile(project_dir: str | Path) -> str:
    """프로젝트 타입 자동 감지 → project-profiles.yml의 profile name 반환"""
    root = Path(project_dir)

    # python-cli
    if (root / "pyproject.toml").exists() or (root / "setup.py").exists():
        return "python-cli"

    # nextjs-app
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            import json
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "next" in deps:
                return "nextjs-app"
        except Exception:
            pass

    # rust-system
    if (root / "Cargo.toml").exists():
        return "rust-system"

    # monorepo
    for f in ("turbo.json", "pnpm-workspace.yaml", "nx.json", "lerna.json"):
        if (root / f).exists():
            return "monorepo"

    return "generic"


def detect_eco_mode() -> str:
    """eco mode 자동 선택 (환경변수 우선)"""
    if mode := os.environ.get("AIDEN_ECO_MODE"):
        return mode
    if os.environ.get("CI"):
        return "eco-2"
    return "default"


def resolve_plugin_root() -> Path:
    """PLUGIN_ROOT 결정: env var → __file__ 기반 fallback.

    path_abstraction.py 가 lib/ 안에 있으므로:
      Path(__file__).resolve().parent  = lib/
      Path(__file__).resolve().parent.parent = plugin root
    """
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent


def resolve_project_root() -> Path:
    """PROJECT_ROOT 결정: env var → cwd fallback.

    우선순위:
    1. CLAUDE_PROJECT_DIR env var
    2. 현재 작업 디렉토리 (os.getcwd())
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    return Path(os.getcwd())


def detect_runtime(project_dir: str | None = None) -> Runtime:
    """전체 런타임 감지 → Runtime 객체 반환"""
    pd = project_dir or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    os_name = detect_os()

    if os_name == "windows":
        shell = "powershell"
        sep = "\\"
        null_dev = "$null"
        python_exe = shutil.which("python") or "python"
    else:
        shell = "bash"
        sep = "/"
        null_dev = "/dev/null"
        python_exe = shutil.which("python3") or "python3"

    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent))

    return Runtime(
        os=os_name,
        shell=shell,
        path_separator=sep,
        null_device=null_dev,
        python_executable=python_exe,
        plugin_root=normalize_path(plugin_root),
        project_dir=normalize_path(pd),
        profile=detect_project_profile(pd),
        eco_mode=detect_eco_mode(),
    )


def write_runtime_file(runtime: Runtime, out_path: str | Path) -> None:
    """state/runtime.yml에 감지 결과 기록"""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# state/runtime.yml — 세션 시작 시 자동 감지 (60분 TTL)", ""]
    for k, v in runtime.to_dict().items():
        lines.append(f"{k}: {v}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    """단독 실행 시 현재 환경 감지 결과 출력"""
    rt = detect_runtime()
    print("=== aiden-auto runtime detection ===")
    for k, v in rt.to_dict().items():
        print(f"  {k:18}: {v}")

    out = Path(rt.plugin_root) / "state" / "runtime.yml"
    write_runtime_file(rt, out)
    print(f"\nWritten: {normalize_path(out)}")


if __name__ == "__main__":
    main()
