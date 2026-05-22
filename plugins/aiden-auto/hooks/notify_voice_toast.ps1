# notify_voice_toast.ps1 — Static helper for notify_voice.py
#
# Shows a Windows Toast notification via BurntToast module.
# Falls back gracefully via Write-Error when BurntToast is unavailable —
# the calling subprocess captures stderr to DEVNULL so failure is silent.
#
# M2 (2026-05-19): Migrated from inline PowerShell `-Command` script in
# notify_voice.py:212-227 to a static `.ps1` file invoked with `-File` + argv.
# Title/Body are passed as proper parameters, eliminating the manual
# `replace("'", "''")` single-quote doubling pattern that was fragile under
# argv parsing edge cases.

param(
    [Parameter(Mandatory=$true)][string]$Title,
    [Parameter(Mandatory=$true)][string]$Body,
    [switch]$Silent
)

try {
    Import-Module BurntToast -ErrorAction Stop
    if ($Silent) {
        New-BurntToastNotification -Text $Title, $Body -Silent
    } else {
        New-BurntToastNotification -Text $Title, $Body -Sound Default
    }
} catch {
    Write-Error $_
}
