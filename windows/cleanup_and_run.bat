@echo off
chcp 65001 >nul
set PYTHONUNBUFFERED=1
cd /d "%~dp0"

echo === copy-hack cleanup_and_run ===
echo Killing old copy_hack python processes...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python' -and $_.CommandLine -match 'copy_hack' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host ('killed PID '+$_.ProcessId) }"

echo Wiping old config...
if exist "%LOCALAPPDATA%\TypewriterPaste" rd /s /q "%LOCALAPPDATA%\TypewriterPaste"

echo Starting with python -u (unbuffered)...
python -u copy_hack.py
echo EXIT CODE %ERRORLEVEL%
pause
