@echo off
chcp 65001 > nul
title Market Scout Agent – Stop

echo ============================================================
echo   Market Scout Agent – Container stoppen
echo   (Daten und Konfiguration bleiben erhalten)
echo ============================================================
echo.

cd /d "%~dp0"

docker info >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Docker laeuft nicht. Bitte Docker Desktop starten.
    pause
    exit /b 1
)

echo [INFO] Container werden gestoppt...
docker-compose stop

echo.
echo [OK] Alle Container gestoppt.
echo      Deine Daten und Einstellungen sind weiterhin vorhanden.
echo      Zum Neustart: start.bat ausfuehren.
echo.
pause
