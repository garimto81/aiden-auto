@echo off
REM _silent_wrap.cmd — diagnostic wrapper for all Claude Code hooks
REM
REM Purpose: capture stderr of any hook to a trace log file while passing
REM stdin/stdout through unchanged. The trace log preserves error source
REM (timestamp + which hook was invoked) for post-hoc root cause analysis
REM of the 'M' is not recognized leak.
REM
REM Usage in settings.json:
REM   "command": "C:/Users/AidenKim/.claude/hooks/_silent_wrap.cmd python \"...\""
REM
REM How it works:
REM   - %* expands to all original arguments (quoted args preserved by cmd.exe)
REM   - 2>> appends stderr to log file (does NOT suppress, just redirects from console)
REM   - stdin / stdout / exitcode all pass through unchanged
REM
REM Created: 2026-05-19 (M-error diagnosis phase)

%* 2>> "%USERPROFILE%\.claude\logs\hook-stderr-trace.log"
