@echo off
setlocal
cd /d "%~dp0"

if not exist "logs" mkdir "logs"

set "PYEXE=pythonw"
if exist ".venv\Scripts\pythonw.exe" set "PYEXE=.venv\Scripts\pythonw.exe"
if not exist ".venv\Scripts\pythonw.exe" (
  where pythonw >nul 2>nul
  if errorlevel 1 set "PYEXE=python"
)

rem Start the server without a visible console window.
start "" /b "%PYEXE%" app.py >> "logs\app.log" 2>&1
endlocal
