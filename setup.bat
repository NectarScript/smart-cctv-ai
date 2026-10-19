@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo === Smart CCTV AI :: setup ===

where python >nul 2>&1 || (echo [ERR] python not on PATH ^(install Python 3.11^)& exit /b 1)

rem --- Python 3.11 guard ---------------------------------------------------
rem Torch cu121 wheels for 2.5.1 only exist for Python 3.9-3.12. The plan
rem pins 3.11. Fail fast with a clear message instead of a cryptic pip error.
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [i] detected python %PYVER%
echo %PYVER% | findstr /r "^3\.11\." >nul
if errorlevel 1 (
  echo [ERR] Python 3.11.x required, found %PYVER%.
  echo       1^) install Python 3.11.9: https://www.python.org/downloads/release/python-3119/
  echo       2^) rmdir /s /q .venv
  echo       3^) py -3.11 -m venv .venv
  echo       4^) run setup.bat again
  exit /b 1
)
rem ------------------------------------------------------------------------
where node   >nul 2>&1 || (echo [ERR] node not on PATH ^(install Node 20 LTS^)   & exit /b 1)
where npm    >nul 2>&1 || (echo [ERR] npm not on PATH                              & exit /b 1)
where git    >nul 2>&1 || (echo [ERR] git not on PATH                              & exit /b 1)

echo [1/6] creating venv...
if not exist ".venv" (
  python -m venv .venv || (echo [ERR] venv create failed & exit /b 1)
)
call .venv\Scripts\activate.bat || (echo [ERR] venv activate failed & exit /b 1)
python -m pip install --upgrade pip wheel

echo [2/6] installing PyTorch CUDA 12.1 (fits RTX 4050)...
pip install --index-url https://download.pytorch.org/whl/cu121 ^
  torch==2.5.1 torchvision==0.20.1 || (echo [ERR] torch install failed & exit /b 1)

echo [3/6] installing python requirements...
pip install -r requirements.txt || (echo [ERR] pip install failed & exit /b 1)

echo [4/6] fetching YOLO weights into .\models ...
if not exist "models" mkdir models
if not exist "models\yolo11n.pt" (
  python -c "from ultralytics import YOLO; m=YOLO('yolo11n.pt'); import shutil, pathlib; shutil.copy(m.ckpt_path, pathlib.Path('models/yolo11n.pt'))" ^
    || (echo [WARN] yolo11n auto-download failed; ultralytics will fetch at first run)
)
if not exist "models\yolo11n-pose.pt" (
  python -c "from ultralytics import YOLO; m=YOLO('yolo11n-pose.pt'); import shutil, pathlib; shutil.copy(m.ckpt_path, pathlib.Path('models/yolo11n-pose.pt'))" ^
    || (echo [WARN] yolo11n-pose auto-download failed; ultralytics will fetch at first run)
)

echo [5/6] checking Ollama + VLM (M2 - skip failures)...
where ollama >nul 2>&1 && (ollama pull qwen2.5vl:3b 2>nul) || echo [WARN] ollama not found; M2 features will stay off

echo [6/6] building dashboard...
pushd frontend
if not exist "node_modules" (
  call npm ci || (echo [ERR] npm ci failed & popd & exit /b 1)
)
call npm run build || (echo [ERR] npm run build failed & popd & exit /b 1)
popd

if not exist ".env" (
  copy /y ".env.example" ".env" >nul
  echo [i] copied .env.example to .env - edit it to add TELEGRAM_BOT_TOKEN later
)

echo === setup OK ===
echo next: run.bat
exit /b 0
