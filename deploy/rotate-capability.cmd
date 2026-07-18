@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0rotate-capability.ps1" %*
exit /b %ERRORLEVEL%
