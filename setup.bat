@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo === Smart CCTV AI :: setup ===

where node   >nul 2>&1 || (echo [ERR] node not on PATH ^(install Node 20 LTS^)   & exit /b 1)
where npm    >nul 2>&1 || (echo [ERR] npm not on PATH                              & exit /b 1)
where git    >nul 2>&1 || (echo [ERR] git not on PATH                              & exit /b 1)

echo [1/6] creating venv (python 3.11)...
if not exist ".venv" (
  where py >nul 2>&1 && (
    py -3.11 -m venv .venv
  ) || (
    where python >nul 2>&1 || (echo [ERR] no python on PATH ^& exit /b 1)
    python -m venv .venv
  )
  if not exist ".venv\Scripts\activate.bat" (
    echo [ERR] venv create failed
    echo       install Python 3.11.9: https://www.python.org/downloads/release/python-3119/
    exit /b 1
  )
)
call .venv\Scripts\activate.bat || (echo [ERR] venv activate failed & exit /b 1)

rem --- venv python 3.11 guard ---------------------------------------------
rem Torch cu121 wheels for 2.5.1 only exist for Python 3.9-3.12. Plan pins
rem 3.11. Fail fast if the venv was built with the wrong interpreter.
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [i] venv python %PYVER%
echo %PYVER% | findstr /r "^3\.11\." >nul
if errorlevel 1 (
  echo [ERR] venv was built with Python %PYVER%, need 3.11.x
  echo       install Python 3.11.9: https://www.python.org/downloads/release/python-3119/
  echo       then:  rmdir /s /q .venv  ^&^&  py -3.11 -m venv .venv  ^&^&  setup.bat
  exit /b 1
)
rem ------------------------------------------------------------------------

python -m pip install --upgrade pip wheel

echo [2/6] installing PyTorch (auto-pick wheel for GPU generation)...
rem RTX 40-series (Ada, sm_89) works with cu121 + torch 2.5.1.
rem RTX 50-series (Blackwell, sm_120) needs cu128 + torch 2.7+.
rem Detect via nvidia-smi; default to cu121 if detection fails.
set TORCH_IDX=https://download.pytorch.org/whl/cu121
set TORCH_PKG=torch==2.5.1 torchvision==0.20.1
for /f "tokens=*" %%g in ('nvidia-smi --query-gpu^=name --format^=csv^,noheader 2^>nul') do set GPU=%%g
echo [i] detected GPU: %GPU%
echo %GPU% | findstr /i "RTX 50" >nul
if not errorlevel 1 (
  echo [i] Blackwell GPU detected - using cu128 wheels
  set TORCH_IDX=https://download.pytorch.org/whl/cu128
  set TORCH_PKG=torch==2.7.0 torchvision==0.22.0
)
pip install --index-url %TORCH_IDX% %TORCH_PKG% ^
  || (echo [ERR] torch install failed & exit /b 1)

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

echo [5/6] checking Ollama (optional; no auto-pull - avoids Windows handle hang)...
where ollama >nul 2>&1 && (echo [i] ollama on PATH - run 'ollama pull qwen2.5vl:3b' later for VLM/chat) ^
  || echo [WARN] ollama not found; VLM + chat agent will stay off

echo [6/6] building dashboard...
pushd frontend
if not exist "node_modules" (
  if exist "package-lock.json" (
    call npm ci || (echo [ERR] npm ci failed & popd & exit /b 1)
  ) else (
    call npm install || (echo [ERR] npm install failed & popd & exit /b 1)
  )
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
