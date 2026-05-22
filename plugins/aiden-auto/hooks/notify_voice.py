#!/usr/bin/env python3
"""Notification hook: 다중 VSCode + Claude Code 음성 알림.

Claude가 사용자 입력/권한을 기다릴 때 stdin으로 hook payload를 받아
- cwd → git repo basename으로 프로젝트 식별
- repo 이름을 hash로 Edge Neural Voice 8개 풀에 매핑 (overrides 우선)
- Edge TTS로 영어 음성 합성 + PowerShell MediaPlayer 재생
- BurntToast로 Windows Toast 동시 표시 (시각 백업)

hook timeout(3초)을 초과하지 않도록 실제 합성/재생은 detached 자식 프로세스에 위임.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
CONFIG_PATH = HOOK_DIR / "_voice_config.json"
LOG_DIR = HOOK_DIR.parent / "logs"
LOG_PATH = LOG_DIR / "notifications.jsonl"

# M1/M2 (2026-05-19): Static PowerShell helper scripts invoked with -File + argv.
# Replaces inline multi-statement PowerShell `-Command` scripts that were fragile
# under argv serialization (root cause of `'M' is not recognized` errors when
# quote/backtick escape fragmented).
PLAY_MP3_PS1 = HOOK_DIR / "play_mp3_mci.ps1"
TOAST_PS1 = HOOK_DIR / "notify_voice_toast.ps1"

DEFAULT_VOICE_POOL = [
    "en-US-AriaNeural",
    "en-US-GuyNeural",
    "en-US-JennyNeural",
    "en-IE-EmilyNeural",
    "en-GB-SoniaNeural",
    "en-GB-RyanNeural",
    "en-AU-NatashaNeural",
    "en-CA-LiamNeural",
]

# Windows process creation flags.
# CREATE_NO_WINDOW prevents console-subsystem children (python.exe, powershell.exe,
# git.exe) from allocating a visible console window. DETACHED_PROCESS is intentionally
# NOT used because, despite "detaching" from the parent console, Windows still creates
# a fresh console for console-mode children, which causes the visible flash.
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200


def _silent_subprocess_kwargs() -> dict:
    """Return kwargs that suppress any console window for subprocess calls on Windows.

    Combines CREATE_NO_WINDOW (no console allocation) with STARTUPINFO(SW_HIDE)
    for belt-and-suspenders coverage across CreateProcess paths.
    """
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0  # SW_HIDE
    return {
        "startupinfo": startupinfo,
        "creationflags": CREATE_NO_WINDOW,
    }


def _windowless_python() -> str:
    """Locate pythonw.exe (GUI-subsystem Python) next to sys.executable.

    pythonw.exe is the canonical Windows interpreter for headless background
    work — it has no console subsystem at all, so no window can ever appear,
    even if a downstream library tries to AllocConsole. Falls back to
    sys.executable when pythonw.exe isn't available (e.g. embedded Python).
    """
    exe = Path(sys.executable)
    candidate = exe.with_name("pythonw.exe")
    if candidate.exists():
        return str(candidate)
    return sys.executable


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "voice_pool": DEFAULT_VOICE_POOL,
        "overrides": {},
        "rate": "+10%",
        "volume": "+0%",
    }


def detect_repo_name(cwd: str) -> str:
    cwd_path = Path(cwd) if cwd else Path.cwd()
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd_path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
            **_silent_subprocess_kwargs(),
        )
        if result.returncode == 0:
            top = result.stdout.strip()
            if top:
                return Path(top).name
    except Exception:
        pass
    return cwd_path.name or "unknown"


def pick_voice(repo_name: str, config: dict) -> str:
    overrides = config.get("overrides") or {}
    if repo_name in overrides:
        return overrides[repo_name]
    pool = config.get("voice_pool") or DEFAULT_VOICE_POOL
    if not pool:
        pool = DEFAULT_VOICE_POOL
    digest = hashlib.md5(repo_name.encode("utf-8")).hexdigest()
    idx = int(digest[:8], 16) % len(pool)
    return pool[idx]


async def _synth_async(text: str, voice: str, rate: str, volume: str, out_path: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, volume=volume)
    await communicate.save(str(out_path))


def synthesize_mp3(text: str, voice: str, config: dict) -> Path | None:
    rate = config.get("rate", "+0%")
    volume = config.get("volume", "+0%")
    fd, raw_path = tempfile.mkstemp(suffix=".mp3", prefix="claude_notify_")
    os.close(fd)
    out_path = Path(raw_path)
    try:
        asyncio.run(_synth_async(text, voice, rate, volume, out_path))
        return out_path
    except Exception as exc:
        print(f"[notify_voice] TTS synthesis failed: {exc}", file=sys.stderr)
        try:
            out_path.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def _play_mp3_ctypes(mp3_path: Path) -> None:
    """L1 primary path: winmm.dll mciSendStringW via ctypes.

    No PowerShell subprocess = no console host spawning = no popup window.
    No argv serialization = no `'M' is not recognized` escape risk.
    """
    import ctypes
    winmm = ctypes.WinDLL("winmm.dll")
    alias = f"snd_{os.getpid()}_{uuid.uuid4().hex[:8]}"
    ret_buf = ctypes.create_unicode_buffer(256)
    cmd_open = f'open "{mp3_path}" type mpegvideo alias {alias}'
    cmd_play = f'play {alias} wait'
    cmd_close = f'close {alias}'
    try:
        rc = winmm.mciSendStringW(cmd_open, ret_buf, 256, None)
        if rc != 0:
            raise RuntimeError(f"MCI open rc={rc}")
        rc = winmm.mciSendStringW(cmd_play, ret_buf, 256, None)
        if rc != 0:
            raise RuntimeError(f"MCI play rc={rc}")
    finally:
        winmm.mciSendStringW(cmd_close, ret_buf, 256, None)


def _play_mp3_ps_fallback(mp3_path: Path) -> None:
    """L1 fallback path: static play_mp3_mci.ps1 via subprocess + argv.

    Used only if the ctypes primary path fails (e.g., non-Windows env,
    DLL load error). Inherits M3's argv safety guarantees.
    """
    subprocess.run(
        [
            "powershell", "-NoProfile", "-NonInteractive",
            "-WindowStyle", "Hidden",
            "-File", str(PLAY_MP3_PS1),
            "-Path", str(mp3_path),
        ],
        capture_output=True,
        timeout=15,
        stdin=subprocess.DEVNULL,
        **_silent_subprocess_kwargs(),
    )


def play_mp3(mp3_path: Path) -> None:
    """MP3 동기 재생 (Windows MCI / winmm.dll mciSendString).

    `play <alias> wait` primes the audio device + decoder + render pipeline
    internally before sending the first frame, so the head-clipping artifact
    from the previous WPF MediaPlayer implementation does not occur.
    Alias is uniquified with PID + GUID to prevent concurrent-notification
    collision.

    L1 (2026-05-19): PowerShell subprocess elimination — primary path uses
    ctypes to call winmm.dll directly, removing the entire PowerShell console
    host spawning + argv escape risk class. Static play_mp3_mci.ps1 retained
    as a fallback for environments where ctypes path raises (defense-in-depth).
    """
    if sys.platform != "win32":
        return
    try:
        _play_mp3_ctypes(mp3_path)
    except Exception as exc:
        print(f"[notify_voice] ctypes play failed, falling back to PS helper: {exc}", file=sys.stderr)
        try:
            _play_mp3_ps_fallback(mp3_path)
        except Exception as exc2:
            print(f"[notify_voice] PS fallback also failed: {exc2}", file=sys.stderr)


def show_toast(repo_name: str, voice_failed: bool, *, silent: bool = True) -> None:
    """BurntToast로 Windows 알림. 별도 PowerShell 프로세스로 비동기.

    silent=True (default, 정상 경로): 토스트 사운드 억제. TTS 음성이 청각 채널을
    이미 사용하므로 Windows 기본 알림음("딩")을 동시에 울리면 사용자에게 두 번
    호출되는 것처럼 들리는 회귀를 방지한다.

    silent=False (TTS 실패 fallback): 토스트 기본 사운드를 재생하여 음성 알림이
    실패한 경우에도 최소 한 번의 청각 피드백은 보장한다.
    """
    body = f"{repo_name} is waiting for your input"
    if voice_failed:
        body += " (voice failed)"

    # M3 (2026-05-19): Static `notify_voice_toast.ps1` + argv replaces inline
    # `-Command` script. -Title / -Body / -Silent (switch) are received as
    # proper PowerShell parameters, eliminating the manual single-quote
    # doubling pattern that was fragile under argv parsing.
    args = [
        "powershell", "-NoProfile", "-NonInteractive",
        "-WindowStyle", "Hidden",
        "-File", str(TOAST_PS1),
        "-Title", "Claude Code",
        "-Body", body,
    ]
    if silent:
        args.append("-Silent")

    try:
        toast_kwargs = _silent_subprocess_kwargs()
        if sys.platform == "win32":
            toast_kwargs["creationflags"] = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            **toast_kwargs,
        )
    except Exception as exc:
        print(f"[notify_voice] toast failed: {exc}", file=sys.stderr)


def append_log(payload: dict) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def run_background(data: dict) -> int:
    """detached 자식 프로세스에서 실제 합성/재생/Toast/로그를 수행."""
    cwd = data.get("cwd") or os.getcwd()
    config = load_config()
    repo_name = detect_repo_name(cwd)
    voice = pick_voice(repo_name, config)
    text = f"{repo_name} is waiting for your input"

    # 정상 경로 토스트는 항상 silent — TTS 음성이 청각 채널을 담당.
    show_toast(repo_name, voice_failed=False, silent=True)

    voice_failed = False
    mp3 = synthesize_mp3(text, voice, config)
    if mp3 is None:
        voice_failed = True
        # TTS 합성 실패 시에만 토스트 기본 사운드로 청각 피드백 보장.
        show_toast(repo_name, voice_failed=True, silent=False)
    else:
        play_mp3(mp3)
        try:
            mp3.unlink(missing_ok=True)
        except Exception:
            pass

    append_log({
        "ts": datetime.now(timezone.utc).isoformat(),
        "cwd": cwd,
        "repo": repo_name,
        "voice": voice,
        "voice_failed": voice_failed,
        "session_id": data.get("session_id"),
        "hook_event_name": data.get("hook_event_name"),
    })
    return 0


def main() -> int:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    if "--background" in sys.argv or os.environ.get("NOTIFY_VOICE_BG") == "1":
        return run_background(data)

    payload = json.dumps(data, ensure_ascii=False)
    try:
        spawn_kwargs = _silent_subprocess_kwargs()
        if sys.platform == "win32":
            spawn_kwargs["creationflags"] = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        # Prefer pythonw.exe on Windows (GUI-subsystem Python — never allocates a
        # console even if some downstream code re-attaches). Falls back to sys.executable.
        interpreter = _windowless_python() if sys.platform == "win32" else sys.executable
        proc = subprocess.Popen(
            [interpreter, __file__, "--background"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            **spawn_kwargs,
        )
        if proc.stdin is not None:
            proc.stdin.write(payload.encode("utf-8"))
            proc.stdin.close()
    except Exception as exc:
        print(f"[notify_voice] spawn failed: {exc}", file=sys.stderr)
        return run_background(data)

    return 0


if __name__ == "__main__":
    sys.exit(main())
