@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 launcher.py check
) else (
    python launcher.py check
)
if errorlevel 1 echo The command did not finish. Read the message above and START-HERE.md.
echo.
pause
