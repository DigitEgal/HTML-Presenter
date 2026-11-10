@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo  Presentation Toolbox - Installation
echo ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [FEHLER] Python wurde nicht gefunden. Bitte Python 3.10+ installieren und PATH setzen.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Erstelle virtuelle Umgebung .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [FEHLER] Konnte virtuelle Umgebung nicht erstellen.
        pause
        exit /b 1
    )
)

echo Installiere Abhaengigkeiten aus requirements.txt...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [WARNUNG] Installation aus requirements.txt fehlgeschlagen, versuche Kernpakete einzeln...
    ".venv\Scripts\python.exe" -m pip install Flask markdown pypdf pymupdf python-pptx
    if errorlevel 1 (
        echo [FEHLER] Installation der Abhaengigkeiten fehlgeschlagen.
        echo Bitte Internetverbindung/Proxy pruefen und install.bat erneut ausfuehren.
        pause
        exit /b 1
    )
)

echo.
echo Pruefe Extraktions-Bibliotheken...
".venv\Scripts\python.exe" -c "import pypdf" >nul 2>nul
if errorlevel 1 (
    echo [WARNUNG] pypdf ist nicht verfuegbar. PDF-Textextraktion kann eingeschraenkt sein.
) else (
    echo [OK] pypdf verfuegbar.
)
".venv\Scripts\python.exe" -c "import pymupdf" >nul 2>nul
if errorlevel 1 (
    echo [WARNUNG] pymupdf ist nicht verfuegbar. PDF-Designerkennung ist eingeschraenkt.
) else (
    echo [OK] pymupdf verfuegbar.
)
".venv\Scripts\python.exe" -c "import pptx" >nul 2>nul
if errorlevel 1 (
    echo [WARNUNG] python-pptx ist nicht verfuegbar. PPTX-Analyse ist eingeschraenkt.
) else (
    echo [OK] python-pptx verfuegbar.
)

echo.
echo Installation abgeschlossen.
echo Starten Sie die Anwendung mit start.bat (verwendet .venv, dort sind die Pakete installiert).
echo.
pause
endlocal
