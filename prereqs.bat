@echo off
rem Smart CCTV AI :: prerequisite installer (double-click or .\prereqs.bat)
rem Delegates to the PowerShell script so we can use winget cleanly.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0prereqs.ps1" %*
exit /b %ERRORLEVEL%
