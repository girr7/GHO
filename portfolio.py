from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

from logger import get_logger

logger = get_logger("portfolio")
STATE_FILE = "portfolio_state.json"


@dataclass
class Trade:
    symbol: str
    side: str             # BUY or SELL
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    order_id: int
    opened_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    closed_at: Optional[str] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None


class Portfolio:
    """Tracks open/closed trades and persists state to disk."""

    def __init__(self) -> None:
        self.open_trades: list[Trade] = []
        self.closed_trades: list[Trade] = []
        self._load()

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        state = {
            "open_trades": [asdict(t) for t in self.open_trades],
            "closed_trades": [asdict(t) for t in self.closed_trades],
        }
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    def _load(self) -> None:
        if not os.path.exists(STATE_FILE):
            return
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
            self.open_trades = [Trade(**t) for t in state.get("open_trades", [])]
            self.closed_trades = [Trade(**t) for t in state.get("closed_trades", [])]
            logger.info(
                "Portfolio loaded — %d open, %d closed trades",
                len(self.open_trades), len(self.closed_trades),
            )
        except Exception as exc:
            logger.warning("Could not load portfolio state: %s", exc)

    # ------------------------------------------------------------------
    # Trade management
    # ------------------------------------------------------------------

    def add_trade(self, trade: Trade) -> None:
        self.open_trades.append(trade)
        self._save()
        logger.info(
            "Trade opened — %s %s qty=%.8f entry=%.4f SL=%.4f TP=%.4f",
            trade.side, trade.symbol, trade.quantity,
            trade.entry_price, trade.stop_loss, trade.take_profit,
        )

    def close_trade(self, trade: Trade, exit_price: float) -> None:
        trade.exit_price = exit_price
        trade.closed_at = datetime.utcnow().isoformat()
        if trade.side == "BUY":
            trade.pnl = (exit_price - trade.entry_price) * trade.quantity
        else:
            trade.pnl = (trade.entry_price - exit_price) * trade.quantity

        self.open_trades.remove(trade)
        self.closed_trades.append(trade)
        self._save()
        logger.info(
            "Trade closed — %s exit=%.4f PnL=%.4f",
            trade.symbol, exit_price, trade.pnl,
        )

    def has_open_trade(self, symbol: str) -> bool:
        return any(t.symbol == symbol for t in self.open_trades)

    def get_open_trade(self, symbol: str) -> Optional[Trade]:
        for t in self.open_trades:
            if t.symbol == symbol:
                return t
        return None

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        total_pnl = sum(t.pnl or 0 for t in self.closed_trades)
        wins = [t for t in self.closed_trades if (t.pnl or 0) > 0]
        win_rate = len(wins) / len(self.closed_trades) * 100 if self.closed_trades else 0
        return {
            "open_trades": len(self.open_trades),
            "closed_trades": len(self.closed_trades),
            "total_pnl": round(total_pnl, 4),
            "win_rate": round(win_rate, 1),
        }
