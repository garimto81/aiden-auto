@echo off
set TID=%RANDOM%-%RANDOM%
echo BEGIN cmd: %* > "%USERPROFILE%\.claude\logs\trace\hook-%TID%.log"
cmd /c %* 2>> "%USERPROFILE%\.claude\logs\trace\hook-%TID%.log"
set EC=%ERRORLEVEL%
echo END exit=%EC% >> "%USERPROFILE%\.claude\logs\trace\hook-%TID%.log"
exit /b %EC%
