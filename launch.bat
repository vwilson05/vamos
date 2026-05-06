@echo off
REM Windows double-click launcher. Same as launch.ps1 but invocable from Explorer.
REM macOS users: see launch.command.

cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -NoProfile -File ".\launch.ps1" %*
if errorlevel 1 pause
