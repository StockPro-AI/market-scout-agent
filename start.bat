@echo off
chcp 65001 > nul
title Market Scout Agent – Windows Starter

echo ============================================================
echo   Market Scout Agent – Automatischer Windows-Setup
echo ============================================================
echo.

:: Ins Verzeichnis der BAT-Datei wechseln
cd /d "%~dp0"

:: ── 1. Git prüfen ──────────────────────────────────────────
where git >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Git ist nicht installiert.
    echo Bitte installiere Git von https://git-scm.com/download/win
    echo Danach diese Datei erneut starten.
    start https://git-scm.com/download/win
    pause
    exit /b 1
)

:: ── 2. Docker prüfen ───────────────────────────────────────
where docker >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Docker ist nicht installiert oder nicht gestartet.
    echo Bitte installiere Docker Desktop von https://www.docker.com/products/docker-desktop
    start https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Docker laeuft nicht. Bitte Docker Desktop starten und erneut versuchen.
    pause
    exit /b 1
)

echo [OK] Docker laeuft.
echo.

:: ── 3. .env erstellen, falls nicht vorhanden ───────────────
if not exist ".env" (
    echo [INFO] .env Datei wird erstellt...
    copy ".env.example" ".env" >nul
    echo [INFO] Oeffne .env in Notepad – bitte API Keys eintragen und speichern.
    echo.
    notepad .env
    echo.
    echo Bitte speichere die .env Datei und druecke dann eine Taste zum Fortfahren...
    pause
) else (
    echo [OK] .env Datei gefunden.
)

echo.

:: ── 4. Docker Image bauen und Agent starten ────────────────
echo [INFO] Docker Image wird gebaut und Agent gestartet...
echo        (Beim ersten Start kann das einige Minuten dauern)
echo.

docker-compose up --build

echo.
echo ============================================================
echo   Agent wurde beendet.
echo   Zum Neustart: start.bat erneut ausfuehren
echo ============================================================
pause
