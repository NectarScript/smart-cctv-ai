@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo [ERR] venv missing - run setup.bat first
  exit /b 1
)
call .venv\Scripts\activate.bat

if not exist "logs" mkdir logs
echo === Smart CCTV AI :: run (Ctrl+C to stop) ===
python -m smart_cctv_ai
exit /b %ERRORLEVEL%
