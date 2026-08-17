@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\portable-app.ps1" start %*
exit /b %ERRORLEVEL%
