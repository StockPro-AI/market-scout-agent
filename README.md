# Market Scout Agent

AI-gestützter Markt-Scanner für professionelle Trader. Der Agent analysiert Finanzmärkte, identifiziert hochwahrscheinliche Trading-Setups und liefert strukturierte **Opportunity Cards** — der Trader entscheidet und führt manuell aus.

## Features

- Scannt eine konfigurierbare Watchlist (Aktien, Indizes, Crypto)
- Filterung nach ungewöhnlichem Volumen (RVOL), Momentum und Relative Strength
- Setup-Erkennung: Breakout, Pullback, Trend-Fortsetzung, Reversal
- Zeitfenster-Logik: Nur in aktiven Marktphasen (erste 2-3h / letzte 90min)
- Max. 3 Opportunity Cards pro Tag
- LLM-gestützte Zusammenfassung auf Deutsch (OpenAI / Anthropic / Gemini)
- Ausgabe: Terminal-Dashboard (Rich) oder Telegram
- Audit-Log in SQLite
- Docker-ready

## Datenquellen

| Quelle | Pflicht | Beschreibung |
|---|---|---|
| Finnhub | Optional | Kurse, Volumen, Fundamentaldaten |
| Alpha Vantage | Optional | Technische Indikatoren, Intradaydaten |

Mindestens eine Datenquelle muss konfiguriert sein.

## Windows Schnellstart (Empfohlen für Einsteiger)

> **Kein Vorwissen nötig!** Einfach `start.bat` doppelklicken — der Assistent erledigt alles automatisch.

### Voraussetzungen

1. **Git** installieren: https://git-scm.com/download/win
2. **Docker Desktop** installieren: https://www.docker.com/products/docker-desktop
3. Docker Desktop starten (Tray-Icon muss grün sein)

### Starten

```
1. Repository klonen oder als ZIP herunterladen
2. In den Ordner wechseln
3. start.bat doppelklicken
```

Die `start.bat` erledigt automatisch:
- Prüft ob Git und Docker installiert sind (mit Download-Link falls nicht)
- Erstellt die `.env` Datei aus dem Beispiel
- Öffnet Notepad zum Eintragen der API Keys
- Baut das Docker Image und startet den Agent

**Beim ersten Start:** Docker lädt alle Abhängigkeiten herunter (ca. 2-5 Minuten).

## Schnellstart (Linux / macOS / erfahrene Nutzer)

```bash
git clone https://github.com/StockPro-AI/market-scout-agent
cd market-scout-agent
cp .env.example .env
# API Keys in .env eintragen
pip install -r requirements.txt
python market_scout.py
```

## Docker

```bash
cp .env.example .env
# API Keys in .env eintragen
docker-compose up --build
```

## Konfiguration

Alle Einstellungen in der `.env`-Datei. Siehe `.env.example` für alle verfügbaren Optionen.

## Projektstruktur

```
market-scout-agent/
├── start.bat              # Windows One-Click-Starter für Einsteiger
├── market_scout.py        # Main Runner
├── src/
│   ├── __init__.py
│   ├── scanner.py         # Markt-Scanner & Watchlist-Filterung
│   ├── analyzer.py        # Setup-Analyse & Scoring
│   ├── risk_checker.py    # Risiko- & Session-Validierung
│   ├── summarizer.py      # LLM-Zusammenfassung & Opportunity Cards
│   └── output.py          # Terminal-Dashboard, Telegram, SQLite-Log
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Was dieser Agent NICHT tut

- Keine automatische Orderausführung
- Keine Broker-API-Anbindung
- Kein 24/7-Dauerbetrieb
- Keine eigenständigen Handelsentscheidungen

## Lizenz

MIT License
