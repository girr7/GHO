from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd
import ta

from config import config
from logger import get_logger

logger = get_logger("strategy")


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class AnalysisResult:
    signal: Signal
    rsi: Optional[float]
    ma_fast: Optional[float]
    ma_slow: Optional[float]
    price: float
    reason: str


def build_dataframe(klines: list) -> pd.DataFrame:
    """Convert raw Binance klines to a DataFrame with OHLCV columns."""
    df = pd.DataFrame(
        klines,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades",
            "taker_base", "taker_quote", "ignore",
        ],
    )
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
    return df


def _rsi_signal(df: pd.DataFrame) -> tuple[Signal, float, str]:
    rsi_series = ta.momentum.RSIIndicator(df["close"], window=config.RSI_PERIOD).rsi()
    rsi = rsi_series.iloc[-1]

    if rsi <= config.RSI_OVERSOLD:
        return Signal.BUY, rsi, f"RSI oversold ({rsi:.1f} <= {config.RSI_OVERSOLD})"
    if rsi >= config.RSI_OVERBOUGHT:
        return Signal.SELL, rsi, f"RSI overbought ({rsi:.1f} >= {config.RSI_OVERBOUGHT})"
    return Signal.HOLD, rsi, f"RSI neutral ({rsi:.1f})"


def _ma_crossover_signal(df: pd.DataFrame) -> tuple[Signal, float, float, str]:
    ma_fast = df["close"].ewm(span=config.MA_FAST, adjust=False).mean()
    ma_slow = df["close"].ewm(span=config.MA_SLOW, adjust=False).mean()

    prev_fast, prev_slow = ma_fast.iloc[-2], ma_slow.iloc[-2]
    curr_fast, curr_slow = ma_fast.iloc[-1], ma_slow.iloc[-1]

    if prev_fast <= prev_slow and curr_fast > curr_slow:
        return Signal.BUY, curr_fast, curr_slow, "EMA crossover upward (golden cross)"
    if prev_fast >= prev_slow and curr_fast < curr_slow:
        return Signal.SELL, curr_fast, curr_slow, "EMA crossover downward (death cross)"
    return Signal.HOLD, curr_fast, curr_slow, "No EMA crossover"


def analyze(klines: list) -> AnalysisResult:
    """Run the configured strategy and return a trading signal."""
    df = build_dataframe(klines)
    price = df["close"].iloc[-1]

    rsi_val: Optional[float] = None
    ma_fast_val: Optional[float] = None
    ma_slow_val: Optional[float] = None

    if config.STRATEGY == "rsi":
        signal, rsi_val, reason = _rsi_signal(df)

    elif config.STRATEGY == "ma_crossover":
        signal, ma_fast_val, ma_slow_val, reason = _ma_crossover_signal(df)

    else:  # combined
        rsi_sig, rsi_val, rsi_reason = _rsi_signal(df)
        ma_sig, ma_fast_val, ma_slow_val, ma_reason = _ma_crossover_signal(df)

        if rsi_sig == Signal.BUY and ma_sig == Signal.BUY:
            signal = Signal.BUY
            reason = f"{rsi_reason} | {ma_reason}"
        elif rsi_sig == Signal.SELL and ma_sig == Signal.SELL:
            signal = Signal.SELL
            reason = f"{rsi_reason} | {ma_reason}"
        else:
            signal = Signal.HOLD
            reason = f"Signals conflict — RSI: {rsi_reason}, MA: {ma_reason}"

    result = AnalysisResult(
        signal=signal,
        rsi=rsi_val,
        ma_fast=ma_fast_val,
        ma_slow=ma_slow_val,
        price=price,
        reason=reason,
    )
    logger.debug("Analysis: %s | Price=%.4f | %s", signal.value, price, reason)
    return result
