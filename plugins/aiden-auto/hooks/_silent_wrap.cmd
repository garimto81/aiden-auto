@echo off
REM ===========================================================================
REM  _silent_wrap.cmd — DEPRECATED 2026-05-22
REM
REM  Project settings.json wrapper hooks were migrated to dispatcher.py registry
REM  pattern (C:/claude/.claude/hooks/registry/{event}/*.json).
REM
REM  This wrapper is no longer invoked by any active hook. File preserved for:
REM    1. Rollback safety (settings.json.bak.silent-wrap-removal exists)
REM    2. SSOT v3.7 "Removal isn't the answer" policy compliance
REM    3. Historical reference (git blame)
REM
REM  Related: docs/02-design/silent-wrap-m-error-resolution.design.md
REM ===========================================================================
set TID=%RANDOM%-%RANDOM%
echo BEGIN cmd: %* > "%USERPROFILE%\.claude\logs\trace\hook-%TID%.log"
cmd /c %* 2>> "%USERPROFILE%\.claude\logs\trace\hook-%TID%.log"
set EC=%ERRORLEVEL%
echo END exit=%EC% >> "%USERPROFILE%\.claude\logs\trace\hook-%TID%.log"
exit /b %EC%
