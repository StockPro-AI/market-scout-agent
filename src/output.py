"""
Output Handler - Module 5
Terminal dashboard (Rich), SQLite logging, optional Telegram delivery.
"""

import os
import json
import sqlite3
from typing import List
from datetime import datetime
from loguru import logger

from src.summarizer import OpportunityCard


class OutputHandler:
    """Handles all output: terminal, database, telegram."""

    def __init__(self):
        self.enable_terminal = os.getenv("ENABLE_TERMINAL_DASHBOARD", "true").lower() == "true"
        self.enable_telegram = os.getenv("ENABLE_TELEGRAM", "false").lower() == "true"
        self.db_path = os.getenv("DB_PATH", "data/signals.db")
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else "data", exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database."""
        try:
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
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"DB init fehler: {e}")

    def _trend_icon(self, trend: str) -> str:
        if trend == "up":
            return "[bold green]LONG[/bold green]"
        elif trend == "down":
            return "[bold red]SHORT[/bold red]"
        return "[yellow]NEUTRAL[/yellow]"

    def _confidence_color(self, confidence: int) -> str:
        if confidence >= 75:
            return f"[bold green]{confidence}[/bold green]"
        elif confidence >= 55:
            return f"[yellow]{confidence}[/yellow]"
        return f"[red]{confidence}[/red]"

    def display_cards(self, cards: List[OpportunityCard]) -> None:
        """Display Opportunity Cards in terminal using Rich."""
        if not self.enable_terminal or not cards:
            return

        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table
            from rich.text import Text
            from rich import box

            console = Console()
            console.print()
            console.print(f"[bold cyan]Market Scout Agent[/bold cyan] - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            console.print(f"[dim]{len(cards)} Opportunity Card(s)[/dim]")
            console.print()

            for i, card in enumerate(cards, 1):
                # Header
                direction = self._trend_icon(card.trend_direction)
                confidence_str = self._confidence_color(card.confidence)

                header = f"[bold]#{i} {card.symbol}[/bold] | {card.company_name} | {direction} | Konfidenz: {confidence_str}/100"

                # Data table
                table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
                table.add_column("Key", style="dim", width=18)
                table.add_column("Value", style="bold")

                table.add_row("Kurs", f"${card.current_price:.2f} ({card.change_pct:+.2f}%)")  
                table.add_row("RVOL", f"{card.rvol:.2f}x")
                table.add_row("Setup", card.setup_type)
                table.add_row("Warum jetzt?", card.why_now)
                table.add_row("Einstieg", card.entry_scenario)
                table.add_row("Entry Zone", card.entry_zone)
                table.add_row("Stop Loss", f"[red]{card.stop_loss}[/red]")
                table.add_row("Target 1", f"[green]{card.target_1}[/green]")
                table.add_row("Target 2", f"[green]{card.target_2}[/green]")
                table.add_row("Invalidierung", card.invalidation)
                table.add_row("Session", card.session_window)
                if card.flags:
                    table.add_row("Flags", " | ".join(card.flags))
                table.add_row("Begruendung", card.llm_reasoning)
                table.add_row("Risikohinweis", f"[yellow]{card.risk_warning}[/yellow]")

                panel = Panel(
                    table,
                    title=header,
                    border_style="cyan",
                    padding=(1, 2)
                )
                console.print(panel)
                console.print()

            console.print("[dim]HINWEIS: Diese Empfehlungen sind keine Anlageberatung. Der Trader entscheidet eigenstaendig.[/dim]")
            console.print()

        except ImportError:
            # Fallback ohne Rich
            print(f"\n=== Market Scout Agent - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
            for i, card in enumerate(cards, 1):
                print(f"\n--- Card #{i}: {card.symbol} ---")
                print(f"Kurs: ${card.current_price:.2f} ({card.change_pct:+.2f}%)")
                print(f"Setup: {card.setup_type} | Konfidenz: {card.confidence}/100")
                print(f"Warum: {card.why_now}")
                print(f"Entry: {card.entry_zone} | SL: {card.stop_loss} | T1: {card.target_1} | T2: {card.target_2}")
                print(f"Risikohinweis: {card.risk_warning}")

    def save_to_db(self, cards: List[OpportunityCard]) -> None:
        """Save cards to SQLite database."""
        if not cards:
            return
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            for card in cards:
                cursor.execute(
                    "INSERT INTO signals (symbol, setup_type, confidence, card_json, created_at) VALUES (?, ?, ?, ?, ?)",
                    (
                        card.symbol,
                        card.setup_type,
                        card.confidence,
                        json.dumps(card.to_dict(), ensure_ascii=False),
                        card.created_at or datetime.now().isoformat(),
                    )
                )
            conn.commit()
            conn.close()
            logger.info(f"{len(cards)} Card(s) in DB gespeichert.")
        except Exception as e:
            logger.error(f"DB speichern fehler: {e}")

    def send_telegram(self, cards: List[OpportunityCard]) -> None:
        """Send cards via Telegram bot if configured."""
        if not self.enable_telegram or not cards:
            return
        if not self.telegram_token or not self.telegram_chat_id:
            logger.warning("Telegram aktiviert aber Token/ChatID fehlt.")
            return

        try:
            import requests
            for card in cards:
                direction = "LONG" if card.trend_direction == "up" else "SHORT" if card.trend_direction == "down" else "NEUTRAL"
                flags_str = " | ".join(card.flags) if card.flags else ""

                msg = (
                    f"*Market Scout Agent*\n"
                    f"*{card.symbol}* - {card.company_name}\n"
                    f"Kurs: ${card.current_price:.2f} ({card.change_pct:+.2f}%)\n"
                    f"Setup: {card.setup_type} | {direction} | Konfidenz: {card.confidence}/100\n"
                    f"RVOL: {card.rvol:.2f}x\n\n"
                    f"*Warum jetzt?*\n{card.why_now}\n\n"
                    f"*Einstieg:* {card.entry_zone}\n"
                    f"*Stop Loss:* {card.stop_loss}\n"
                    f"*Target 1:* {card.target_1}\n"
                    f"*Target 2:* {card.target_2}\n"
                    f"*Invalidierung:* {card.invalidation}\n\n"
                    f"*Begruendung:*\n{card.llm_reasoning}\n\n"
                    f"_Risikohinweis: {card.risk_warning}_"
                )
                if flags_str:
                    msg += f"\nFlags: {flags_str}"

                url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                response = requests.post(url, json={
                    "chat_id": self.telegram_chat_id,
                    "text": msg,
                    "parse_mode": "Markdown"
                }, timeout=10)

                if response.status_code == 200:
                    logger.info(f"Telegram: Card fuer {card.symbol} gesendet.")
                else:
                    logger.error(f"Telegram fehler: {response.status_code} - {response.text[:100]}")

        except Exception as e:
            logger.error(f"Telegram send fehler: {e}")

    # Status messages
    def show_inactive_session(self) -> None:
        if self.enable_terminal:
            try:
                from rich.console import Console
                Console().print("[dim]Market Scout: Kein aktives Handelsfenster. Naechster Check spaeter.[/dim]")
            except ImportError:
                print("Market Scout: Kein aktives Handelsfenster.")

    def show_daily_limit_reached(self) -> None:
        if self.enable_terminal:
            try:
                from rich.console import Console
                Console().print("[yellow]Market Scout: Tageslimit fuer Opportunity Cards erreicht.[/yellow]")
            except ImportError:
                print("Market Scout: Tageslimit erreicht.")

    def show_no_candidates(self) -> None:
        if self.enable_terminal:
            try:
                from rich.console import Console
                Console().print("[dim]Market Scout: Keine Kandidaten im aktuellen Scan.[/dim]")
            except ImportError:
                print("Market Scout: Keine Kandidaten gefunden.")

    def show_no_setups(self) -> None:
        if self.enable_terminal:
            try:
                from rich.console import Console
                Console().print("[dim]Market Scout: Keine validen Setups nach Analyse.[/dim]")
            except ImportError:
                print("Market Scout: Keine validen Setups.")

    def show_no_approved(self) -> None:
        if self.enable_terminal:
            try:
                from rich.console import Console
                Console().print("[dim]Market Scout: Kein Kandidat hat den Risiko-Check bestanden.[/dim]")
            except ImportError:
                print("Market Scout: Kein Kandidat hat Risk-Check bestanden.")
