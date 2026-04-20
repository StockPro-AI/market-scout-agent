"""
LLM Summarizer - Module 4
Creates structured Opportunity Cards using LLM (OpenAI / Anthropic / Gemini).
All output is in German for the trader.
"""

import os
import json
from dataclasses import dataclass
from typing import List, Optional
from loguru import logger

from src.analyzer import ScoredCandidate


@dataclass
class OpportunityCard:
    """A structured trading opportunity card for the human trader."""
    symbol: str
    company_name: str
    current_price: float
    setup_type: str
    confidence: int
    trend_direction: str
    # LLM-generated content
    why_now: str
    entry_scenario: str
    entry_zone: str
    stop_loss: str
    target_1: str
    target_2: str
    invalidation: str
    session_window: str
    risk_warning: str
    llm_reasoning: str
    # Raw data
    change_pct: float
    rvol: float
    flags: List[str]
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "company_name": self.company_name,
            "current_price": self.current_price,
            "setup_type": self.setup_type,
            "confidence": self.confidence,
            "trend_direction": self.trend_direction,
            "why_now": self.why_now,
            "entry_scenario": self.entry_scenario,
            "entry_zone": self.entry_zone,
            "stop_loss": self.stop_loss,
            "target_1": self.target_1,
            "target_2": self.target_2,
            "invalidation": self.invalidation,
            "session_window": self.session_window,
            "risk_warning": self.risk_warning,
            "llm_reasoning": self.llm_reasoning,
            "change_pct": self.change_pct,
            "rvol": self.rvol,
            "flags": self.flags,
            "created_at": self.created_at,
        }


class LLMSummarizer:
    """Creates Opportunity Cards using the configured LLM provider."""

    SYSTEM_PROMPT = """Du bist ein erfahrener Trading-Analyst. 
Deine Aufgabe ist es, strukturierte Opportunity Cards fuer professionelle Trader zu erstellen.
Du analysierst Marktdaten objektiv und lieferst praezise, umsetzbare Empfehlungen auf Deutsch.
Du gibst KEINE Garantien und weist immer auf Risiken hin.
Du empfiehlst NIEMALS automatisches Trading - der Trader entscheidet immer selbst."""

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "openai").lower()
        self.max_daily_cards = int(os.getenv("MAX_DAILY_CARDS", "3"))

    def _build_prompt(self, candidate: ScoredCandidate) -> str:
        c = candidate.candidate
        direction = "LONG" if candidate.trend_direction == "up" else "SHORT" if candidate.trend_direction == "down" else "NEUTRAL"

        return f"""Erstelle eine Opportunity Card fuer diesen Kandidaten:

Symbol: {c.symbol}
Unternehmen: {c.description or c.symbol}
Sektor: {c.sector or 'unbekannt'}
Aktueller Kurs: ${c.price:.2f}
Kursaenderung: {c.change_pct:+.2f}%
Relatives Volumen (RVOL): {c.rvol:.2f}x
Intraday Range: ${c.low:.2f} - ${c.high:.2f}

Setup-Analyse:
- Setup-Typ: {candidate.setup_type}
- Trend: {candidate.trend_direction} ({direction})
- Konfidenz-Score: {candidate.confidence}/100
- Einstiegszone: {candidate.entry_zone}
- Stop Loss: {candidate.stop_loss}
- Target 1: {candidate.target_1}
- Target 2: {candidate.target_2}
- Invalidierung: {candidate.invalidation}
- Flags: {', '.join(candidate.flags) if candidate.flags else 'keine'}

Bitte erstelle eine strukturierte Opportunity Card mit folgenden Feldern (antworte NUR mit validem JSON):
{{
  "why_now": "1-2 Saetze: Warum ist dieses Asset JETZT interessant?",
  "entry_scenario": "Konkretes Einstiegsszenario in 1-2 Saetzen",
  "session_window": "Empfohlenes Handelsfenster (Morgen/Abend/beide)",
  "risk_warning": "Spezifischer Risikohinweis fuer dieses Setup",
  "llm_reasoning": "2-3 Saetze: Qualitative Begruendung der Opportunity"
}}"""

    def _call_openai(self, prompt: str) -> Optional[str]:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            model = os.getenv("OPENAI_MODEL", "gpt-4o")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=600,
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI Fehler: {e}")
            return None

    def _call_anthropic(self, prompt: str) -> Optional[str]:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
            message = client.messages.create(
                model=model,
                max_tokens=600,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Anthropic Fehler: {e}")
            return None

    def _call_gemini(self, prompt: str) -> Optional[str]:
        try:
            import google.generativeai as genai
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model = genai.GenerativeModel(
                model_name=os.getenv("GEMINI_MODEL", "gemini-1.5-pro"),
                system_instruction=self.SYSTEM_PROMPT
            )
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini Fehler: {e}")
            return None

    def _call_llm(self, prompt: str) -> Optional[dict]:
        """Call the configured LLM and parse JSON response."""
        raw = None
        if self.provider == "openai":
            raw = self._call_openai(prompt)
        elif self.provider == "anthropic":
            raw = self._call_anthropic(prompt)
        elif self.provider == "gemini":
            raw = self._call_gemini(prompt)
        else:
            logger.error(f"Unbekannter LLM Provider: {self.provider}")
            return None

        if not raw:
            return None

        try:
            # Extract JSON from response
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            return json.loads(raw)
        except Exception as e:
            logger.error(f"JSON-Parse Fehler: {e}\nRaw: {raw[:200]}")
            return None

    def _create_fallback_card(self, candidate: ScoredCandidate) -> dict:
        """Create a basic card without LLM if API call fails."""
        direction = "LONG" if candidate.trend_direction == "up" else "SHORT"
        return {
            "why_now": f"{candidate.symbol} zeigt ungewoehnliche Aktivitaet mit RVOL {candidate.candidate.rvol:.1f}x und {candidate.candidate.change_pct:+.1f}% Kursaenderung.",
            "entry_scenario": f"{direction}-Setup: {candidate.setup_type} mit Einstieg in {candidate.entry_zone}.",
            "session_window": "Aktive Marktphase (Morgen/Abend)",
            "risk_warning": f"Stop Loss bei {candidate.stop_loss} beachten. Kein Trade ohne Bestaetigung.",
            "llm_reasoning": candidate.reasoning,
        }

    def create_cards(self, candidates: List[ScoredCandidate]) -> List[OpportunityCard]:
        """Create Opportunity Cards for approved candidates."""
        from datetime import datetime
        cards = []

        # Limit to max daily cards
        candidates = candidates[:self.max_daily_cards]

        for candidate in candidates:
            try:
                prompt = self._build_prompt(candidate)
                llm_data = self._call_llm(prompt)

                if not llm_data:
                    logger.warning(f"{candidate.symbol}: LLM-Call fehlgeschlagen, nutze Fallback.")
                    llm_data = self._create_fallback_card(candidate)

                card = OpportunityCard(
                    symbol=candidate.symbol,
                    company_name=candidate.candidate.description or candidate.symbol,
                    current_price=candidate.candidate.price,
                    setup_type=candidate.setup_type,
                    confidence=candidate.confidence,
                    trend_direction=candidate.trend_direction,
                    why_now=llm_data.get("why_now", ""),
                    entry_scenario=llm_data.get("entry_scenario", ""),
                    entry_zone=candidate.entry_zone,
                    stop_loss=candidate.stop_loss,
                    target_1=candidate.target_1,
                    target_2=candidate.target_2,
                    invalidation=candidate.invalidation,
                    session_window=llm_data.get("session_window", "Aktive Marktphase"),
                    risk_warning=llm_data.get("risk_warning", ""),
                    llm_reasoning=llm_data.get("llm_reasoning", ""),
                    change_pct=candidate.candidate.change_pct,
                    rvol=candidate.candidate.rvol,
                    flags=candidate.flags,
                    created_at=datetime.now().isoformat(),
                )
                cards.append(card)
                logger.info(f"Opportunity Card erstellt: {candidate.symbol} ({candidate.setup_type})")

            except Exception as e:
                logger.error(f"Fehler beim Erstellen der Card fuer {candidate.symbol}: {e}")

        return cards
