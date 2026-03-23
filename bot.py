"""
Binance Trading Bot
===================
Main bot loop — fetches candles, runs the strategy, manages orders and
stop-loss / take-profit levels.

Usage:
    python bot.py
"""
from __future__ import annotations

import signal
import sys
import time
from datetime import datetime

import schedule

from config import config
from exchange import BinanceExchange
from logger import get_logger
from portfolio import Portfolio, Trade
from strategy import Signal, analyze

logger = get_logger("bot")


class TradingBot:
    def __init__(self) -> None:
        config.validate()
        self.exchange = BinanceExchange()
        self.portfolio = Portfolio()
        self.running = False

        # Graceful shutdown on SIGINT / SIGTERM
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def _check_pair(self) -> None:
        symbol = config.TRADING_PAIR
        logger.info("--- Checking %s [%s] ---", symbol, datetime.utcnow().isoformat())

        # 1. Check existing open trade for SL/TP
        open_trade = self.portfolio.get_open_trade(symbol)
        if open_trade:
            self._manage_open_trade(open_trade)
            return  # One trade at a time per symbol

        # 2. Respect max open trades limit
        if len(self.portfolio.open_trades) >= config.MAX_OPEN_TRADES:
            logger.info("Max open trades (%d) reached. Skipping.", config.MAX_OPEN_TRADES)
            return

        # 3. Fetch candles and analyse
        klines = self.exchange.get_klines(
            symbol, config.KLINE_INTERVAL, config.KLINE_LIMIT
        )
        result = analyze(klines)
        logger.info(
            "Price=%.4f | Signal=%s | %s",
            result.price, result.signal.value, result.reason,
        )

        # 4. Act on signal
        if result.signal == Signal.BUY:
            self._open_buy(symbol, result.price)
        elif result.signal == Signal.SELL:
            logger.info("SELL signal but no open position — skipping short.")
        else:
            logger.info("Holding — no action taken.")

    def _open_buy(self, symbol: str, price: float) -> None:
        quote_balance = self.exchange.get_balance(config.QUOTE_ASSET)
        if quote_balance < config.TRADE_AMOUNT:
            logger.warning(
                "Insufficient %s balance (%.2f < %.2f). Cannot open trade.",
                config.QUOTE_ASSET, quote_balance, config.TRADE_AMOUNT,
            )
            return

        order = self.exchange.buy_market(symbol, config.TRADE_AMOUNT)
        if order is None:
            return

        # Calculate executed quantity and average fill price
        qty = float(order.get("executedQty", 0))
        if qty == 0:
            logger.warning("Order filled with 0 quantity — skipping trade record.")
            return

        cummulative_quote = float(order.get("cummulativeQuoteQty", config.TRADE_AMOUNT))
        entry_price = cummulative_quote / qty if qty else price

        stop_loss = entry_price * (1 - config.STOP_LOSS_PERCENT / 100)
        take_profit = entry_price * (1 + config.TAKE_PROFIT_PERCENT / 100)

        trade = Trade(
            symbol=symbol,
            side="BUY",
            quantity=qty,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            order_id=int(order["orderId"]),
        )
        self.portfolio.add_trade(trade)

    def _manage_open_trade(self, trade: Trade) -> None:
        price = self.exchange.get_price(trade.symbol)
        logger.info(
            "Open trade — entry=%.4f SL=%.4f TP=%.4f | current=%.4f",
            trade.entry_price, trade.stop_loss, trade.take_profit, price,
        )

        if price <= trade.stop_loss:
            logger.warning("STOP-LOSS hit at %.4f — closing trade.", price)
            self._close_trade(trade, price)
        elif price >= trade.take_profit:
            logger.info("TAKE-PROFIT hit at %.4f — closing trade.", price)
            self._close_trade(trade, price)

    def _close_trade(self, trade: Trade, current_price: float) -> None:
        order = self.exchange.sell_market(trade.symbol, trade.quantity)
        exit_price = current_price
        if order:
            qty = float(order.get("executedQty", trade.quantity))
            cq = float(order.get("cummulativeQuoteQty", 0))
            exit_price = cq / qty if qty else current_price

        self.portfolio.close_trade(trade, exit_price)
        stats = self.portfolio.summary()
        logger.info(
            "Portfolio — closed=%d total_pnl=%.4f win_rate=%.1f%%",
            stats["closed_trades"], stats["total_pnl"], stats["win_rate"],
        )

    # ------------------------------------------------------------------
    # Scheduler / run loop
    # ------------------------------------------------------------------

    def _schedule_jobs(self) -> None:
        interval_map = {
            "1m": 1, "3m": 3, "5m": 5, "15m": 15,
            "30m": 30, "1h": 60, "4h": 240,
        }
        minutes = interval_map.get(config.KLINE_INTERVAL, 15)
        schedule.every(minutes).minutes.do(self._check_pair)
        logger.info(
            "Scheduled checks every %d minute(s) for %s",
            minutes, config.TRADING_PAIR,
        )

    def run(self) -> None:
        logger.info("=" * 60)
        logger.info(" Binance Trading Bot starting")
        logger.info(" Pair    : %s", config.TRADING_PAIR)
        logger.info(" Strategy: %s", config.STRATEGY)
        logger.info(" Interval: %s", config.KLINE_INTERVAL)
        logger.info(" Testnet : %s", config.USE_TESTNET)
        logger.info("=" * 60)

        self._schedule_jobs()
        self.running = True

        # Run once immediately, then on schedule
        self._check_pair()

        while self.running:
            schedule.run_pending()
            time.sleep(1)

    def _shutdown(self, *_) -> None:
        logger.info("Shutdown signal received — stopping bot.")
        self.running = False
        stats = self.portfolio.summary()
        logger.info(
            "Final stats — open=%d closed=%d total_pnl=%.4f win_rate=%.1f%%",
            stats["open_trades"], stats["closed_trades"],
            stats["total_pnl"], stats["win_rate"],
        )
        sys.exit(0)


if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
