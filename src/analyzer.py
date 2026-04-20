"""
Setup Analyzer - Module 2
Analyzes scanner candidates, identifies setup types and assigns confidence scores.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from loguru import logger

from src.scanner import Candidate


@dataclass
class ScoredCandidate:
    """A candidate with setup analysis and confidence score."""
    candidate: Candidate
    setup_type: str
    confidence: int  # 0-100
    trend_direction: str  # "up" | "down" | "sideways"
    entry_zone: str
    stop_loss: str
    target_1: str
    target_2: str
    invalidation: str
    reasoning: str
    flags: List[str] = field(default_factory=list)

    @property
    def symbol(self) -> str:
        return self.candidate.symbol

    @property
    def risk_reward(self) -> float:
        """Estimated Risk/Reward ratio from setup."""
        try:
            price = self.candidate.price
            entry = float(self.entry_zone.split("-")[0].replace("$", "").strip())
            stop = float(self.stop_loss.replace("$", "").replace("under", "").strip().split()[0])
            t1 = float(self.target_1.replace("$", "").strip().split()[0])
            risk = abs(entry - stop)
            reward = abs(t1 - entry)
            if risk == 0:
                return 0.0
            return round(reward / risk, 2)
        except Exception:
            return 0.0


class SetupAnalyzer:
    """Analyzes candidates and scores their setups."""

    SETUP_TYPES = [
        "Breakout",
        "Pullback zum Trendlevel",
        "Trend-Fortsetzung",
        "Reversal",
        "Range-Ausbruch",
        "Gap-and-Go",
        "VWAP-Bounce",
    ]

    def __init__(self):
        self.alphavantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")

    def _detect_trend(self, candidate: Candidate) -> str:
        """Simple trend detection based on price vs open and change."""
        if candidate.change_pct > 1.0:
            return "up"
        elif candidate.change_pct < -1.0:
            return "down"
        else:
            return "sideways"

    def _get_sma(self, symbol: str, period: int = 20) -> Optional[float]:
        """Get SMA from Alpha Vantage if available."""
        if not self.alphavantage_key:
            return None
        try:
            import requests
            url = (
                f"https://www.alphavantage.co/query?"
                f"function=SMA&symbol={symbol}&interval=daily"
                f"&time_period={period}&series_type=close&apikey={self.alphavantage_key}"
            )
            response = requests.get(url, timeout=8)
            data = response.json()
            values = data.get("Technical Analysis: SMA", {})
            if values:
                latest_key = list(values.keys())[0]
                return float(values[latest_key]["SMA"])
        except Exception as e:
            logger.debug(f"SMA fetch fehler fuer {symbol}: {e}")
        return None

    def _identify_setup(self, candidate: Candidate, trend: str) -> str:
        """Identify the most likely setup type."""
        change = abs(candidate.change_pct)
        range_pct = candidate.range_pct

        # Gap-and-Go: large gap from previous close
        gap_pct = abs((candidate.open - (candidate.price / (1 + candidate.change_pct / 100))) /
                      (candidate.price / (1 + candidate.change_pct / 100)) * 100) if candidate.open > 0 else 0
        if gap_pct > 2.0 and candidate.rvol > 2.0:
            return "Gap-and-Go"

        # Breakout: price near high with high volume
        if candidate.price >= candidate.high * 0.99 and candidate.rvol > 2.0:
            return "Breakout"

        # Reversal: price near low with high volume in downtrend, or near high in uptrend
        if trend == "down" and candidate.price <= candidate.low * 1.01 and candidate.rvol > 1.8:
            return "Reversal"

        # Pullback: strong trend with moderate volume
        if change > 1.5 and candidate.rvol > 1.5:
            return "Pullback zum Trendlevel"

        # Trend continuation
        if change > 0.8 and candidate.rvol >= 1.5:
            return "Trend-Fortsetzung"

        return "Range-Ausbruch"

    def _calculate_levels(self, candidate: Candidate, trend: str) -> dict:
        """Calculate entry, stop, and target levels."""
        price = candidate.price
        high = candidate.high
        low = candidate.low
        spread = high - low if high > low else price * 0.01

        if trend == "up":
            entry_low = round(price * 0.998, 2)
            entry_high = round(price * 1.002, 2)
            stop = round(low * 0.998, 2)
            t1 = round(price + spread * 1.5, 2)
            t2 = round(price + spread * 2.5, 2)
            invalidation = f"Schlusskurs unter ${stop}"
        else:
            entry_low = round(price * 0.998, 2)
            entry_high = round(price * 1.002, 2)
            stop = round(high * 1.002, 2)
            t1 = round(price - spread * 1.5, 2)
            t2 = round(price - spread * 2.5, 2)
            invalidation = f"Schlusskurs ueber ${stop}"

        return {
            "entry_zone": f"${entry_low} - ${entry_high}",
            "stop_loss": f"${stop}",
            "target_1": f"${t1}",
            "target_2": f"${t2}",
            "invalidation": invalidation,
        }

    def _calculate_confidence(self, candidate: Candidate, setup_type: str, trend: str) -> int:
        """Calculate confidence score 0-100."""
        score = 0

        # RVOL scoring (max 30 points)
        if candidate.rvol >= 3.0:
            score += 30
        elif candidate.rvol >= 2.0:
            score += 20
        elif candidate.rvol >= 1.5:
            score += 10

        # Price change scoring (max 25 points)
        change = abs(candidate.change_pct)
        if change >= 5.0:
            score += 25
        elif change >= 3.0:
            score += 18
        elif change >= 1.5:
            score += 12
        elif change >= 0.5:
            score += 6

        # Setup type bonus (max 25 points)
        setup_bonus = {
            "Gap-and-Go": 25,
            "Breakout": 20,
            "Reversal": 18,
            "Trend-Fortsetzung": 15,
            "Pullback zum Trendlevel": 15,
            "VWAP-Bounce": 12,
            "Range-Ausbruch": 10,
        }
        score += setup_bonus.get(setup_type, 10)

        # Clear trend bonus (max 20 points)
        if trend in ("up", "down"):
            score += 20

        return min(score, 100)

    def analyze(self, candidates: List[Candidate]) -> List[ScoredCandidate]:
        """Analyze all candidates and return scored list, sorted by confidence."""
        scored = []

        for candidate in candidates:
            try:
                trend = self._detect_trend(candidate)
                setup_type = self._identify_setup(candidate, trend)
                levels = self._calculate_levels(candidate, trend)
                confidence = self._calculate_confidence(candidate, setup_type, trend)

                reasoning = (
                    f"{candidate.symbol} zeigt {setup_type}-Setup mit "
                    f"{candidate.change_pct:+.2f}% Kursaenderung und RVOL {candidate.rvol:.2f}x. "
                    f"Trend: {trend}. Konfidenz: {confidence}/100."
                )

                flags = []
                if candidate.rvol > 3.0:
                    flags.append("HIGH_VOLUME")
                if abs(candidate.change_pct) > 5.0:
                    flags.append("STRONG_MOVE")
                if setup_type == "Gap-and-Go":
                    flags.append("GAP")

                scored_candidate = ScoredCandidate(
                    candidate=candidate,
                    setup_type=setup_type,
                    confidence=confidence,
                    trend_direction=trend,
                    entry_zone=levels["entry_zone"],
                    stop_loss=levels["stop_loss"],
                    target_1=levels["target_1"],
                    target_2=levels["target_2"],
                    invalidation=levels["invalidation"],
                    reasoning=reasoning,
                    flags=flags,
                )
                scored.append(scored_candidate)
                logger.info(f"{candidate.symbol}: Setup={setup_type}, Konfidenz={confidence}")

            except Exception as e:
                logger.error(f"Analyse-Fehler fuer {candidate.symbol}: {e}")

        # Sort by confidence descending
        scored.sort(key=lambda x: x.confidence, reverse=True)
        return scored
