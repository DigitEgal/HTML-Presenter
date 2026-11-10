@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo  Presentation Toolbox - Deinstallation
echo ==========================================
echo.
echo Dies entfernt die lokale Installationsumgebung (.venv) und Cache-Dateien.
echo Ihre Daten in data\ und exports\ bleiben erhalten.
echo.

choice /M "Deinstallation durchfuehren"
if errorlevel 2 (
  echo Abgebrochen.
  pause
  exit /b 0
)

if exist ".venv" (
  echo Entferne .venv ...
  rmdir /s /q ".venv"
)

echo Entferne Python-Cache ...
for /d /r %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
del /s /q *.pyc >nul 2>nul

echo.
echo Optionale Bereinigung:
choice /M "exports\ (exportierte HTML-Dateien) loeschen"
if not errorlevel 2 (
  if exist "exports" rmdir /s /q "exports"
  mkdir "exports" >nul 2>nul
)

echo.
choice /M "data\ (Designs, Praesentationen, Einstellungen) loeschen"
if not errorlevel 2 (
  if exist "data" rmdir /s /q "data"
)

echo.
echo Deinstallation abgeschlossen.
echo.
pause
endlocal
