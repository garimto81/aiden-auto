#!/usr/bin/env python3
"""tts_generate.py — edge-tts wrapper for peon-ping dynamic TTS.

L3 (2026-05-19): Python port of tts-generate.ps1. Invoked via pythonw.exe
(GUI subsystem — no console allocation ever) from peon.ps1 when the TTS
cache misses. This replaces the entire `Start-Process powershell` chain,
eliminating the last PowerShell subprocess that could spawn a console host
window in the peon-ping flow.

Generates MP3 from text template, caches in tts-cache/{project}/{category}.mp3.

Usage:
  pythonw tts_generate.py <project> <display_name> <category> <voice> <template> <output_dir>

Argv ordering matches peon.ps1 $argList exactly. All values are passed as
Python list elements (subprocess.list2cmdline handles quoting), so drive
letters, spaces, and special characters are safe.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path


def _log(log_file: Path, line: str) -> None:
    try:
        with log_file.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")
    except Exception:
        pass


async def _synth(text: str, voice: str, out_path: str) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(out_path)


def main() -> int:
    if len(sys.argv) != 7:
        return 1
    project, display_name, category, voice, template, output_dir = sys.argv[1:]

    project_dir = Path(output_dir) / project
    output_file = project_dir / f"{category}.mp3"

    # Skip if already cached (idempotent — peon.ps1 already checks but
    # double-check here for safety against race conditions).
    if output_file.exists():
        return 0

    project_dir.mkdir(parents=True, exist_ok=True)
    message = template.replace("{project}", display_name)

    # peon-ping/tts-generate.log — shared log with the legacy .ps1 wrapper
    install_dir = Path(__file__).resolve().parent.parent  # peon-ping/
    log_file = install_dir / "tts-generate.log"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        asyncio.run(_synth(message, voice, str(output_file)))
        _log(log_file, f"[{ts}] OK: {project}/{category} -> {output_file}")
        return 0
    except Exception as exc:
        _log(log_file, f"[{ts}] FAIL: {project}/{category} - {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
