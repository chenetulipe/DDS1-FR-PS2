@echo off
echo ============================================
echo   DDS1 Tool - Digital Devil Saga FR
echo ============================================
echo.

cd /d "%~dp0dds1_tool"

:: Verifier que Python est installe
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR: Python non trouve. Installez Python 3.10+
    pause
    exit /b 1
)

:: Installer les dependances si besoin
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo Installation des dependances...
    pip install fastapi uvicorn python-multipart --quiet
)

echo.
echo Lancement du serveur...
echo Ouvrez votre navigateur sur : http://localhost:8000
echo.
echo (Ctrl+C pour arreter)
echo.

:: Tuer tout process sur le port 8000 d'abord
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)

python backend\server.py
pause
