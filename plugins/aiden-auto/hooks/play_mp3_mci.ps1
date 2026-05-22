# play_mp3_mci.ps1 — Static helper for notify_voice.py
#
# Plays an MP3 file synchronously via Windows MCI (winmm.dll mciSendString).
# `play <alias> wait` primes the audio device + decoder + render pipeline
# internally before sending the first frame, so the head-clipping artifact
# from the previous WPF MediaPlayer implementation does not occur.
# Alias is uniquified with PID + GUID to prevent collision when multiple
# notifications fire concurrently.
#
# M1 (2026-05-19): Migrated from inline PowerShell `-Command` script in
# notify_voice.py:162-191 to a static `.ps1` file invoked with `-File` + argv.
# This eliminates quote/backtick escape risk in subprocess argv serialization.
# The previous pattern was the root cause of `'M' is not recognized` errors
# when argv parsing fragmented under Windows drive paths or special chars.

param(
    [Parameter(Mandatory=$true)][string]$Path
)

$ErrorActionPreference = 'Stop'

Add-Type -Name NotifyMci -Namespace Win32 -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("winmm.dll", CharSet=System.Runtime.InteropServices.CharSet.Unicode)]
public static extern int mciSendString(string command, System.Text.StringBuilder ret, int retLen, System.IntPtr hwnd);
'@

$alias = "snd_$($PID)_$([guid]::NewGuid().ToString('N').Substring(0,8))"
$ret = New-Object System.Text.StringBuilder 256

try {
    $r = [Win32.NotifyMci]::mciSendString("open `"$Path`" type mpegvideo alias $alias", $ret, $ret.Capacity, [System.IntPtr]::Zero)
    if ($r -ne 0) { throw "MCI open rc=$r" }
    $r = [Win32.NotifyMci]::mciSendString("play $alias wait", $ret, $ret.Capacity, [System.IntPtr]::Zero)
    if ($r -ne 0) { throw "MCI play rc=$r" }
} finally {
    [void][Win32.NotifyMci]::mciSendString("close $alias", $ret, $ret.Capacity, [System.IntPtr]::Zero)
}
