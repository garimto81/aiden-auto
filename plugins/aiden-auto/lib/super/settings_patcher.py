"""Settings Patcher — `.claude/settings.json` 안전 read/write/merge.

핵심 기능:
  - UTF-8 강제 read (cp949 fallback 시도)
  - atomic write (tempfile + rename)
  - JSON merge (기존 키 보존, 새 키만 추가)
  - backup 자동 생성 (1회만)

사용처: auto_install_statusline.py가 settings.json을 자동 patch.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PatchResult:
    patched: bool
    skipped_reason: str = ""
    backup_path: Path | None = None


def read_settings(path: Path) -> dict:
    """UTF-8 강제 read. 실패 시 cp949 fallback. 파일 없으면 {}."""
    if not path.exists():
        return {}
    raw_bytes = path.read_bytes()
    # BOM 제거
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        raw_bytes = raw_bytes[3:]
    for encoding in ("utf-8", "cp949", "utf-16"):
        try:
            text = raw_bytes.decode(encoding)
            return json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise ValueError(f"Cannot decode {path} as JSON in any common encoding")


def atomic_write_json(path: Path, data: dict) -> None:
    """atomic write — tempfile + rename. UTF-8 BOM 없이."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="settings-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


def backup_once(settings_path: Path, backup_path: Path) -> Path | None:
    """backup 파일이 없을 때만 생성. 이미 있으면 None."""
    if backup_path.exists():
        return None
    if not settings_path.exists():
        return None
    shutil.copy2(settings_path, backup_path)
    return backup_path


def merge_patch(base: dict, patch: dict, *, preserve_existing: set[str] | None = None) -> dict:
    """base에 patch를 deep-merge. preserve_existing의 키는 base 값 우선.

    - dict 값은 재귀 merge
    - list 값은 append (중복 제거 X — 사용자 책임)
    - 그 외 (str/int/bool) 는 덮어쓰기 (단 preserve_existing 키는 보존)
    """
    preserve = preserve_existing or set()
    result = dict(base)  # shallow copy

    for k, v in patch.items():
        if k in preserve and k in result:
            continue  # 사용자 customization 우선
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = merge_patch(result[k], v)
        elif isinstance(v, list) and isinstance(result.get(k), list):
            result[k] = result[k] + [x for x in v if x not in result[k]]
        else:
            result[k] = v
    return result


def apply_patch_safely(
    settings_path: Path,
    patch: dict,
    *,
    backup_path: Path | None = None,
    preserve_top_level: set[str] | None = None,
) -> PatchResult:
    """settings.json에 patch 안전 적용.

    Args:
        settings_path: 대상 (.claude/settings.json)
        patch: 추가/병합할 dict
        backup_path: 없으면 settings_path + ".aiden-backup"
        preserve_top_level: 사용자 customization 우선 키 (e.g. {"statusLine"})

    Returns:
        PatchResult
    """
    if backup_path is None:
        backup_path = settings_path.parent / (settings_path.name + ".aiden-backup")

    try:
        current = read_settings(settings_path)
    except Exception as e:
        return PatchResult(patched=False, skipped_reason=f"read failed: {e}")

    # preserve 검사 — 이미 설정된 top-level key는 모두 patch에서 제거 (사용자 우선)
    preserve = preserve_top_level or set()
    effective_patch = dict(patch)
    for k in list(effective_patch.keys()):
        if k in preserve and k in current:
            # 이미 사용자가 customization → 해당 키 patch 제거 (대신 sub-key는 merge 가능)
            # 단순화: 해당 top-level key 자체를 skip
            del effective_patch[k]

    if not effective_patch:
        return PatchResult(patched=False, skipped_reason="all patch keys already user-customized")

    # backup 생성
    backup = backup_once(settings_path, backup_path)

    # merge + write
    merged = merge_patch(current, effective_patch)
    if merged == current:
        return PatchResult(patched=False, skipped_reason="no changes needed", backup_path=backup)

    atomic_write_json(settings_path, merged)
    return PatchResult(patched=True, backup_path=backup)
