from __future__ import annotations

from typing import Optional

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException

from config import config
from logger import get_logger

logger = get_logger("exchange")


class BinanceExchange:
    """Thin wrapper around python-binance Client with error handling."""

    def __init__(self) -> None:
        if config.USE_TESTNET:
            self.client = Client(
                config.API_KEY,
                config.API_SECRET,
                testnet=True,
            )
            logger.info("Connected to Binance TESTNET")
        else:
            self.client = Client(config.API_KEY, config.API_SECRET)
            logger.info("Connected to Binance MAINNET")

        self._ping()

    def _ping(self) -> None:
        self.client.ping()
        server_time = self.client.get_server_time()
        logger.info("Binance ping OK — server time: %s", server_time["serverTime"])

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    def get_klines(self, symbol: str, interval: str, limit: int) -> list:
        return self.client.get_klines(symbol=symbol, interval=interval, limit=limit)

    def get_price(self, symbol: str) -> float:
        ticker = self.client.get_symbol_ticker(symbol=symbol)
        return float(ticker["price"])

    def get_balance(self, asset: str) -> float:
        info = self.client.get_asset_balance(asset=asset)
        if info is None:
            return 0.0
        return float(info["free"])

    def get_symbol_info(self, symbol: str) -> dict:
        return self.client.get_symbol_info(symbol)

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def buy_market(self, symbol: str, quote_qty: float) -> Optional[dict]:
        """Place a market buy order using a fixed quote quantity (e.g. USDT)."""
        try:
            order = self.client.order_market_buy(
                symbol=symbol,
                quoteOrderQty=round(quote_qty, 2),
            )
            logger.info(
                "BUY order placed — id=%s symbol=%s quoteQty=%.2f",
                order["orderId"], symbol, quote_qty,
            )
            return order
        except (BinanceAPIException, BinanceOrderException) as exc:
            logger.error("Failed to place BUY order: %s", exc)
            return None

    def sell_market(self, symbol: str, quantity: float) -> Optional[dict]:
        """Place a market sell order for a specific base asset quantity."""
        try:
            order = self.client.order_market_sell(
                symbol=symbol,
                quantity=quantity,
            )
            logger.info(
                "SELL order placed — id=%s symbol=%s qty=%.8f",
                order["orderId"], symbol, quantity,
            )
            return order
        except (BinanceAPIException, BinanceOrderException) as exc:
            logger.error("Failed to place SELL order: %s", exc)
            return None

    def get_order(self, symbol: str, order_id: int) -> Optional[dict]:
        try:
            return self.client.get_order(symbol=symbol, orderId=order_id)
        except BinanceAPIException as exc:
            logger.error("Failed to get order %s: %s", order_id, exc)
            return None

    def cancel_order(self, symbol: str, order_id: int) -> Optional[dict]:
        try:
            result = self.client.cancel_order(symbol=symbol, orderId=order_id)
            logger.info("Order %s cancelled", order_id)
            return result
        except BinanceAPIException as exc:
            logger.error("Failed to cancel order %s: %s", order_id, exc)
            return None

    def get_open_orders(self, symbol: str) -> list:
        try:
            return self.client.get_open_orders(symbol=symbol)
        except BinanceAPIException as exc:
            logger.error("Failed to get open orders: %s", exc)
            return []
