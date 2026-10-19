@echo off
rem Quick post-setup sanity check. Run from the repo root in one terminal
rem while run.bat is already running in another.
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat

echo === smoke: py_compile ===
python -m py_compile smart_cctv_ai\__init__.py smart_cctv_ai\__main__.py ^
  smart_cctv_ai\config.py smart_cctv_ai\pipeline.py smart_cctv_ai\schema.py ^
  smart_cctv_ai\api\app.py scripts\doctor.py || (echo [FAIL] py_compile & exit /b 1)

echo === smoke: /healthz ===
curl -s -o - --max-time 5 http://127.0.0.1:8000/healthz || (
  echo [WARN] /healthz unreachable - is run.bat running in another window?
)
echo.

echo === smoke: /events ===
curl -s -o - --max-time 5 http://127.0.0.1:8000/events?limit=5
echo.

echo === smoke: /stats ===
curl -s -o - --max-time 5 http://127.0.0.1:8000/stats?hours=24
echo.
exit /b 0
