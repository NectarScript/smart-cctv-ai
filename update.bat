@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo === Smart CCTV AI :: update ===

for /f %%H in ('git rev-parse HEAD') do set BEFORE=%%H
git pull --ff-only || (echo [ERR] git pull failed & exit /b 1)
for /f %%H in ('git rev-parse HEAD') do set AFTER=%%H

if "%BEFORE%"=="%AFTER%" (
  echo [i] no changes
  exit /b 0
)

call .venv\Scripts\activate.bat || (echo [ERR] venv missing - run setup.bat & exit /b 1)

git diff --name-only %BEFORE% %AFTER% > .changed.txt
findstr /i "requirements.txt" .changed.txt >nul && (
  echo [i] requirements changed - reinstalling
  pip install -r requirements.txt || (echo [ERR] pip install failed & exit /b 1)
)
findstr /i "frontend/" .changed.txt >nul && (
  echo [i] frontend changed - rebuilding
  pushd frontend
  if not exist "node_modules" (
    if exist "package-lock.json" (
      call npm ci || (popd & exit /b 1)
    ) else (
      call npm install || (popd & exit /b 1)
    )
  )
  call npm run build || (popd & exit /b 1)
  popd
)
del .changed.txt >nul 2>&1

echo === update OK ===
exit /b 0
