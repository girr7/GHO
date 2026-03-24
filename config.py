import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Binance API
    API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")
    USE_TESTNET: bool = os.getenv("USE_TESTNET", "true").lower() == "true"

    # Trading
    TRADING_PAIR: str = os.getenv("TRADING_PAIR", "BTCUSDT")
    QUOTE_ASSET: str = os.getenv("QUOTE_ASSET", "USDT")
    TRADE_AMOUNT: float = float(os.getenv("TRADE_AMOUNT", "50"))
    STRATEGY: str = os.getenv("STRATEGY", "combined")

    # Risk management
    STOP_LOSS_PERCENT: float = float(os.getenv("STOP_LOSS_PERCENT", "2.0"))
    TAKE_PROFIT_PERCENT: float = float(os.getenv("TAKE_PROFIT_PERCENT", "4.0"))
    MAX_OPEN_TRADES: int = int(os.getenv("MAX_OPEN_TRADES", "3"))

    # Technical indicators
    RSI_PERIOD: int = 14
    RSI_OVERSOLD: float = 30.0
    RSI_OVERBOUGHT: float = 70.0
    MA_FAST: int = 9
    MA_SLOW: int = 21
    KLINE_INTERVAL: str = "1m"   # Candlestick interval
    KLINE_LIMIT: int = 100        # Number of candles to fetch

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = "bot.log"

    def validate(self) -> None:
        if not self.API_KEY or not self.API_SECRET:
            raise ValueError(
                "BINANCE_API_KEY and BINANCE_API_SECRET must be set in .env file"
            )
        if self.TRADE_AMOUNT <= 0:
            raise ValueError("TRADE_AMOUNT must be greater than 0")
        if self.STOP_LOSS_PERCENT <= 0 or self.TAKE_PROFIT_PERCENT <= 0:
            raise ValueError("STOP_LOSS_PERCENT and TAKE_PROFIT_PERCENT must be > 0")
        if self.STRATEGY not in ("rsi", "ma_crossover", "combined"):
            raise ValueError("STRATEGY must be one of: rsi, ma_crossover, combined")


config = Config()
