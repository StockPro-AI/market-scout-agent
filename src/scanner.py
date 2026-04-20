"""
Market Scanner - Module 1
Scans watchlist for candidates based on volume, momentum and relative strength.
Supports Finnhub (primary) and Alpha Vantage (secondary/optional).
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from loguru import logger


@dataclass
class Candidate:
    """A market candidate identified by the scanner."""
    symbol: str
    price: float
    change_pct: float
    volume: float
    avg_volume: float
    rvol: float  # Relative Volume
    high: float
    low: float
    open: float
    market_cap: Optional[float] = None
    description: str = ""
    sector: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def range_pct(self) -> float:
        """Intraday range as percentage of price."""
        if self.price == 0:
            return 0.0
        return ((self.high - self.low) / self.price) * 100


class FinnhubDataSource:
    """Finnhub API data source."""

    def __init__(self):
        self.api_key = os.getenv("FINNHUB_API_KEY")
        if not self.api_key:
            raise ValueError("FINNHUB_API_KEY nicht gesetzt.")
        import finnhub
        self.client = finnhub.Client(api_key=self.api_key)

    def get_quote(self, symbol: str) -> Optional[dict]:
        try:
            quote = self.client.quote(symbol)
            return quote
        except Exception as e:
            logger.warning(f"Finnhub quote fehler fuer {symbol}: {e}")
            return None

    def get_basic_financials(self, symbol: str) -> Optional[dict]:
        try:
            return self.client.company_basic_financials(symbol, 'all')
        except Exception as e:
            logger.warning(f"Finnhub financials fehler fuer {symbol}: {e}")
            return None

    def get_company_profile(self, symbol: str) -> Optional[dict]:
        try:
            return self.client.company_profile2(symbol=symbol)
        except Exception as e:
            logger.warning(f"Finnhub profile fehler fuer {symbol}: {e}")
            return None


class AlphaVantageDataSource:
    """Alpha Vantage API data source (optional)."""

    def __init__(self):
        self.api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        if not self.api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY nicht gesetzt.")

    def get_intraday(self, symbol: str, interval: str = "5min") -> Optional[dict]:
        import requests
        try:
            url = (
                f"https://www.alphavantage.co/query?"
                f"function=TIME_SERIES_INTRADAY&symbol={symbol}"
                f"&interval={interval}&apikey={self.api_key}&outputsize=compact"
            )
            response = requests.get(url, timeout=10)
            data = response.json()
            if "Time Series" in str(data):
                return data
            logger.warning(f"Alpha Vantage kein Intraday fuer {symbol}: {data.get('Note', data.get('Information', 'unknown'))}")
            return None
        except Exception as e:
            logger.warning(f"Alpha Vantage fehler fuer {symbol}: {e}")
            return None

    def get_sma(self, symbol: str, period: int = 20) -> Optional[float]:
        import requests
        try:
            url = (
                f"https://www.alphavantage.co/query?"
                f"function=SMA&symbol={symbol}&interval=daily"
                f"&time_period={period}&series_type=close&apikey={self.api_key}"
            )
            response = requests.get(url, timeout=10)
            data = response.json()
            values = data.get("Technical Analysis: SMA", {})
            if values:
                latest_key = list(values.keys())[0]
                return float(values[latest_key]["SMA"])
            return None
        except Exception as e:
            logger.warning(f"Alpha Vantage SMA fehler fuer {symbol}: {e}")
            return None


class MarketScanner:
    """Main market scanner. Uses available data sources to find candidates."""

    def __init__(self):
        self.watchlist = self._load_watchlist()
        self.min_rvol = float(os.getenv("MIN_RVOL", "1.5"))
        self.min_change_pct = float(os.getenv("MIN_PRICE_CHANGE_PCT", "0.5"))

        # Initialize available data sources
        self.finnhub = None
        self.alphavantage = None

        if os.getenv("FINNHUB_API_KEY"):
            try:
                self.finnhub = FinnhubDataSource()
                logger.info("Finnhub Datenquelle aktiv.")
            except Exception as e:
                logger.error(f"Finnhub init fehlgeschlagen: {e}")

        if os.getenv("ALPHA_VANTAGE_API_KEY"):
            try:
                self.alphavantage = AlphaVantageDataSource()
                logger.info("Alpha Vantage Datenquelle aktiv.")
            except Exception as e:
                logger.error(f"Alpha Vantage init fehlgeschlagen: {e}")

        if not self.finnhub and not self.alphavantage:
            raise RuntimeError("Keine Datenquelle verfuegbar!")

    def _load_watchlist(self) -> List[str]:
        watchlist_str = os.getenv("WATCHLIST", "AAPL,TSLA,NVDA,MSFT,AMZN")
        symbols = [s.strip().upper() for s in watchlist_str.split(",") if s.strip()]
        logger.info(f"Watchlist geladen: {len(symbols)} Symbole")
        return symbols

    def _get_candidate_data(self, symbol: str) -> Optional[Candidate]:
        """Fetch market data for a symbol using available sources."""
        price = change_pct = volume = avg_volume = high = low = open_price = 0.0
        description = sector = ""

        if self.finnhub:
            quote = self.finnhub.get_quote(symbol)
            if not quote or quote.get("c", 0) == 0:
                logger.debug(f"Keine Daten fuer {symbol} von Finnhub.")
                return None

            price = quote.get("c", 0.0)       # current price
            open_price = quote.get("o", 0.0)  # open
            high = quote.get("h", 0.0)        # high
            low = quote.get("l", 0.0)         # low
            prev_close = quote.get("pc", 0.0) # previous close

            if prev_close > 0:
                change_pct = ((price - prev_close) / prev_close) * 100

            # Get basic financials for avg volume
            financials = self.finnhub.get_basic_financials(symbol)
            if financials:
                metric = financials.get("metric", {})
                avg_volume = metric.get("10DayAverageTradingVolume", 0) * 1_000_000

            # Get company profile
            profile = self.finnhub.get_company_profile(symbol)
            if profile:
                description = profile.get("name", symbol)
                sector = profile.get("finnhubIndustry", "")

            # Volume estimation (Finnhub quote does not provide volume directly)
            # Use change magnitude as proxy if avg_volume available
            volume = avg_volume * abs(change_pct / 2) if avg_volume > 0 else 0

        # Calculate RVOL
        rvol = (volume / avg_volume) if avg_volume > 0 else 1.0

        return Candidate(
            symbol=symbol,
            price=price,
            change_pct=change_pct,
            volume=volume,
            avg_volume=avg_volume,
            rvol=rvol,
            high=high,
            low=low,
            open=open_price,
            description=description,
            sector=sector,
        )

    def scan(self) -> List[Candidate]:
        """Scan all watchlist symbols and return filtered candidates."""
        candidates = []

        for symbol in self.watchlist:
            try:
                candidate = self._get_candidate_data(symbol)
                if candidate is None:
                    continue

                # Filter by minimum criteria
                if abs(candidate.change_pct) < self.min_change_pct:
                    logger.debug(f"{symbol}: Preisaenderung {candidate.change_pct:.2f}% zu gering.")
                    continue

                if candidate.rvol < self.min_rvol:
                    logger.debug(f"{symbol}: RVOL {candidate.rvol:.2f} zu gering.")
                    continue

                logger.info(f"Kandidat: {symbol} | {candidate.change_pct:+.2f}% | RVOL: {candidate.rvol:.2f}")
                candidates.append(candidate)

            except Exception as e:
                logger.error(f"Fehler beim Scannen von {symbol}: {e}")

        logger.info(f"Scanner: {len(candidates)} Kandidaten von {len(self.watchlist)} Symbolen")
        return candidates
