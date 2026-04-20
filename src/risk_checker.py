"""
Risk Checker - Module 3
Validates session windows, daily limits, R/R ratios and liquidity.
"""

import os
import sqlite3
from datetime import datetime, date
from typing import List
import pytz
from loguru import logger

from src.analyzer import ScoredCandidate


class RiskChecker:
    """Validates trading session, daily limits, R/R and liquidity."""

    NYSE_TZ = pytz.timezone("America/New_York")

    def __init__(self):
        self.morning_session_hours = float(os.getenv("MORNING_SESSION_HOURS", "2.5"))
        self.evening_session_minutes = float(os.getenv("EVENING_SESSION_MINUTES", "90"))
        self.max_daily_cards = int(os.getenv("MAX_DAILY_CARDS", "3"))
        self.min_rr = float(os.getenv("MIN_RISK_REWARD", "2.0"))
        self.min_avg_volume = float(os.getenv("MIN_AVG_DAILY_VOLUME", "1000000"))
        self.db_path = os.getenv("DB_PATH", "data/signals.db")
        self.force_scan = os.getenv("FORCE_SCAN", "false").lower() == "true"

    def _get_nyse_time(self) -> datetime:
        """Return current time in NYSE timezone."""
        return datetime.now(self.NYSE_TZ)

    def is_active_session(self) -> bool:
        """Check if we are in an active trading session window."""
        if self.force_scan:
            logger.info("FORCE_SCAN aktiv - Zeitfenster wird ignoriert.")
            return True

        now = self._get_nyse_time()
        weekday = now.weekday()  # 0=Monday, 6=Sunday

        # No trading on weekends
        if weekday >= 5:
            logger.info(f"Wochenende ({now.strftime('%A')}) - kein aktives Handelsfenster.")
            return False

        # NYSE market hours: 9:30 - 16:00 ET
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

        if now < market_open or now > market_close:
            logger.info(f"Ausserhalb der Marktzeiten ({now.strftime('%H:%M')} ET).")
            return False

        # Morning session window
        morning_end = market_open.replace(
            minute=int((30 + self.morning_session_hours * 60) % 60),
            hour=market_open.hour + int((30 + self.morning_session_hours * 60) // 60)
        )
        # Simpler: morning session = first N hours after open
        from datetime import timedelta
        morning_window_end = market_open + timedelta(hours=self.morning_session_hours)
        evening_window_start = market_close - timedelta(minutes=self.evening_session_minutes)

        in_morning = market_open <= now <= morning_window_end
        in_evening = evening_window_start <= now <= market_close

        if in_morning:
            logger.info(f"Aktive Morgensession ({now.strftime('%H:%M')} ET).")
            return True
        elif in_evening:
            logger.info(f"Aktive Abendsession ({now.strftime('%H:%M')} ET).")
            return True
        else:
            logger.info(f"Inaktive Mittagszone ({now.strftime('%H:%M')} ET). Scout ist still.")
            return False

    def daily_limit_ok(self) -> bool:
        """Check if daily card limit has been reached."""
        today = date.today().isoformat()
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    setup_type TEXT,
                    confidence INTEGER,
                    card_json TEXT,
                    created_at TEXT
                )
            """)
            cursor.execute(
                "SELECT COUNT(*) FROM signals WHERE DATE(created_at) = ?",
                (today,)
            )
            count = cursor.fetchone()[0]
            conn.close()

            remaining = self.max_daily_cards - count
            if remaining <= 0:
                logger.info(f"Tageslimit erreicht: {count}/{self.max_daily_cards} Cards heute.")
                return False
            logger.info(f"Tageslimit ok: {count}/{self.max_daily_cards} Cards heute ({remaining} verbleibend).")
            return True
        except Exception as e:
            logger.error(f"DB-Fehler bei daily_limit_ok: {e}")
            return True  # Fail open - don't block on DB errors

    def _check_candidate(self, candidate: ScoredCandidate) -> tuple:
        """Check a single candidate. Returns (approved: bool, reason: str)."""
        # Confidence minimum
        if candidate.confidence < 40:
            return False, f"Konfidenz zu niedrig ({candidate.confidence}/100)"

        # Liquidity check
        if candidate.candidate.avg_volume > 0 and candidate.candidate.avg_volume < self.min_avg_volume:
            return False, f"Liquiditaet zu gering (Avg Vol: {candidate.candidate.avg_volume:,.0f})"

        # R/R check
        rr = candidate.risk_reward
        if rr > 0 and rr < self.min_rr:
            return False, f"R/R zu niedrig ({rr:.2f}, Minimum: {self.min_rr})"

        return True, "OK"

    def filter(self, candidates: List[ScoredCandidate]) -> List[ScoredCandidate]:
        """Filter candidates by risk rules. Returns approved list."""
        approved = []
        today_count = self._get_today_count()
        remaining = self.max_daily_cards - today_count

        for candidate in candidates:
            if len(approved) >= remaining:
                logger.info(f"Tageslimit wuerde ueberschritten. Stoppe nach {len(approved)} Kandidaten.")
                break

            ok, reason = self._check_candidate(candidate)
            if ok:
                approved.append(candidate)
                logger.info(f"{candidate.symbol}: Risk-Check bestanden (R/R: {candidate.risk_reward:.2f})")
            else:
                logger.info(f"{candidate.symbol}: Risk-Check nicht bestanden - {reason}")

        return approved

    def _get_today_count(self) -> int:
        """Get count of signals created today."""
        today = date.today().isoformat()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM signals WHERE DATE(created_at) = ?",
                (today,)
            )
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0
