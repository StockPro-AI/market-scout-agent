#!/usr/bin/env python3
"""
Market Scout Agent - Main Runner
AI-powered trading opportunity detector for professional traders.
NO auto-execution. Human-in-the-loop by design.
"""

import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger

from src.scanner import MarketScanner
from src.analyzer import SetupAnalyzer
from src.risk_checker import RiskChecker
from src.summarizer import LLMSummarizer
from src.output import OutputHandler

# Load environment variables
load_dotenv()

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logger.remove()
logger.add(sys.stderr, level=LOG_LEVEL)
logger.add("data/market_scout.log", rotation="1 day", retention="7 days", level=LOG_LEVEL)


def validate_config() -> bool:
    """Validate that at least one data source and one LLM provider is configured."""
    has_data_source = bool(os.getenv("FINNHUB_API_KEY")) or bool(os.getenv("ALPHA_VANTAGE_API_KEY"))
    has_llm = (
        bool(os.getenv("OPENAI_API_KEY")) or
        bool(os.getenv("ANTHROPIC_API_KEY")) or
        bool(os.getenv("GEMINI_API_KEY"))
    )

    if not has_data_source:
        logger.error("Keine Datenquelle konfiguriert! Bitte FINNHUB_API_KEY oder ALPHA_VANTAGE_API_KEY in .env setzen.")
        return False
    if not has_llm:
        logger.error("Kein LLM Provider konfiguriert! Bitte OPENAI_API_KEY, ANTHROPIC_API_KEY oder GEMINI_API_KEY in .env setzen.")
        return False
    return True


def run_scan() -> None:
    """Execute one full scan cycle."""
    logger.info("=" * 60)
    logger.info(f"Market Scout Agent - Scan gestartet: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # Initialize modules
    scanner = MarketScanner()
    analyzer = SetupAnalyzer()
    risk_checker = RiskChecker()
    summarizer = LLMSummarizer()
    output = OutputHandler()

    # Step 1: Check session window
    if not risk_checker.is_active_session():
        logger.info("Kein aktives Handelsfenster. Scout ist still.")
        output.show_inactive_session()
        return

    # Step 2: Check daily card limit
    if not risk_checker.daily_limit_ok():
        logger.info("Tageslimit fuer Opportunity Cards erreicht. Kein weiterer Scan.")
        output.show_daily_limit_reached()
        return

    # Step 3: Scan watchlist
    logger.info("Scanne Watchlist...")
    candidates = scanner.scan()
    if not candidates:
        logger.info("Keine Kandidaten nach Scanner-Filterung gefunden.")
        output.show_no_candidates()
        return
    logger.info(f"{len(candidates)} Kandidaten gefunden nach Scanner-Filterung.")

    # Step 4: Analyze setups
    logger.info("Analysiere Setups...")
    scored_candidates = analyzer.analyze(candidates)
    if not scored_candidates:
        logger.info("Keine validen Setups nach Analyse gefunden.")
        output.show_no_setups()
        return

    # Step 5: Risk check
    logger.info("Risiko-Check...")
    approved = risk_checker.filter(scored_candidates)
    if not approved:
        logger.info("Keine Kandidaten haben den Risiko-Check bestanden.")
        output.show_no_approved()
        return
    logger.info(f"{len(approved)} Kandidaten haben Risiko-Check bestanden.")

    # Step 6: LLM Summarization -> Opportunity Cards
    logger.info("Erstelle Opportunity Cards mit LLM...")
    cards = summarizer.create_cards(approved)
    if not cards:
        logger.warning("LLM Summarizer hat keine Cards erstellt.")
        return

    # Step 7: Output
    output.display_cards(cards)
    output.save_to_db(cards)
    output.send_telegram(cards)

    logger.info(f"Scan abgeschlossen. {len(cards)} Opportunity Card(s) erstellt.")


def main() -> None:
    """Main entry point."""
    # Create data directory
    os.makedirs("data", exist_ok=True)

    # Validate config
    if not validate_config():
        sys.exit(1)

    logger.info("Market Scout Agent gestartet.")
    logger.info(f"LLM Provider: {os.getenv('LLM_PROVIDER', 'openai')}")
    logger.info(f"Datenquellen: Finnhub={'aktiv' if os.getenv('FINNHUB_API_KEY') else 'inaktiv'}, "
                f"Alpha Vantage={'aktiv' if os.getenv('ALPHA_VANTAGE_API_KEY') else 'inaktiv'}")

    # Single run or scheduled?
    import argparse
    parser = argparse.ArgumentParser(description="Market Scout Agent")
    parser.add_argument("--once", action="store_true", help="Einmaliger Scan, kein Scheduling")
    parser.add_argument("--force", action="store_true", help="Scan erzwingen (ignoriert Zeitfenster)")
    args = parser.parse_args()

    if args.force:
        os.environ["FORCE_SCAN"] = "true"

    if args.once:
        run_scan()
    else:
        import schedule
        # Schedule scans every 15 minutes during market hours
        schedule.every(15).minutes.do(run_scan)
        logger.info("Scheduler aktiv. Scan alle 15 Minuten waehrend aktiver Sessions.")
        # Run immediately on start
        run_scan()
        while True:
            schedule.run_pending()
            time.sleep(60)


if __name__ == "__main__":
    main()
