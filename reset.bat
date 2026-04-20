@echo off
chcp 65001 > nul
title Market Scout Agent – Reset

echo ============================================================
echo   Market Scout Agent – Container stoppen und loeschen
echo   !! ACHTUNG: Container werden entfernt !!
echo   (Deine .env und lokalen Dateien bleiben erhalten)
echo ============================================================
echo.

cd /d "%~dp0"

docker info >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Docker laeuft nicht. Bitte Docker Desktop starten.
    pause
    exit /b 1
)

echo [WARNUNG] Dieser Vorgang stoppt und loescht alle Container dieses Projekts.
echo           Deine .env Konfiguration und Datendateien bleiben ERHALTEN.
echo.
set /p CONFIRM=Fortfahren? (j/n): 
if /i not "%CONFIRM%"=="j" (
    echo Abgebrochen.
    pause
    exit /b 0
)

echo.
echo [INFO] Container werden gestoppt und geloescht...
docker-compose down

echo.
echo [OK] Alle Container gestoppt und geloescht.
echo      Deine .env und Datendateien sind weiterhin vorhanden.
echo      Zum Neustart (inkl. neuem Build): start.bat ausfuehren.
echo.
pause
