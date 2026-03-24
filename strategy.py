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
    bb_upper: Optional[float]
    bb_lower: Optional[float]
    volume_ok: bool
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


def _bollinger_signal(df: pd.DataFrame) -> tuple[Signal, float, float, str]:
    """Bollinger Bands confirmation: price outside bands strengthens signals."""
    bb = ta.volatility.BollingerBands(
        df["close"], window=config.BB_PERIOD, window_dev=config.BB_STD_DEV,
    )
    upper = bb.bollinger_hband().iloc[-1]
    lower = bb.bollinger_lband().iloc[-1]
    price = df["close"].iloc[-1]

    if price <= lower:
        return Signal.BUY, upper, lower, f"Price ({price:.2f}) at/below BB lower ({lower:.2f})"
    if price >= upper:
        return Signal.SELL, upper, lower, f"Price ({price:.2f}) at/above BB upper ({upper:.2f})"
    return Signal.HOLD, upper, lower, f"Price ({price:.2f}) within BB ({lower:.2f}-{upper:.2f})"


def _volume_filter(df: pd.DataFrame) -> tuple[bool, str]:
    """Return True if current volume is above threshold * SMA(volume)."""
    vol_sma = df["volume"].rolling(window=config.VOLUME_SMA_PERIOD).mean().iloc[-1]
    current_vol = df["volume"].iloc[-1]
    threshold = vol_sma * config.VOLUME_THRESHOLD

    if current_vol >= threshold:
        return True, f"Vol OK ({current_vol:.0f} >= {threshold:.0f})"
    return False, f"Low vol ({current_vol:.0f} < {threshold:.0f})"


def analyze(klines: list) -> AnalysisResult:
    """Run the configured strategy and return a trading signal."""
    df = build_dataframe(klines)
    price = df["close"].iloc[-1]

    rsi_val: Optional[float] = None
    ma_fast_val: Optional[float] = None
    ma_slow_val: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None

    # Volume filter applies to all strategies
    volume_ok, vol_reason = _volume_filter(df)

    if config.STRATEGY == "rsi":
        signal, rsi_val, reason = _rsi_signal(df)
        if signal != Signal.HOLD and not volume_ok:
            reason = f"{reason} | BLOCKED: {vol_reason}"
            signal = Signal.HOLD

    elif config.STRATEGY == "ma_crossover":
        signal, ma_fast_val, ma_slow_val, reason = _ma_crossover_signal(df)
        if signal != Signal.HOLD and not volume_ok:
            reason = f"{reason} | BLOCKED: {vol_reason}"
            signal = Signal.HOLD

    else:  # combined
        rsi_sig, rsi_val, rsi_reason = _rsi_signal(df)
        ma_sig, ma_fast_val, ma_slow_val, ma_reason = _ma_crossover_signal(df)
        bb_sig, bb_upper, bb_lower, bb_reason = _bollinger_signal(df)

        # BUY: at least 2 of 3 indicators agree + volume confirmation
        buy_count = sum(s == Signal.BUY for s in (rsi_sig, ma_sig, bb_sig))
        sell_count = sum(s == Signal.SELL for s in (rsi_sig, ma_sig, bb_sig))

        parts = f"RSI: {rsi_reason} | MA: {ma_reason} | BB: {bb_reason} | {vol_reason}"

        if buy_count >= 2 and volume_ok:
            signal = Signal.BUY
            reason = parts
        elif sell_count >= 2 and volume_ok:
            signal = Signal.SELL
            reason = parts
        elif (buy_count >= 2 or sell_count >= 2) and not volume_ok:
            signal = Signal.HOLD
            reason = f"Signal found but BLOCKED by volume filter | {parts}"
        else:
            signal = Signal.HOLD
            reason = f"No consensus | {parts}"

    result = AnalysisResult(
        signal=signal,
        rsi=rsi_val,
        ma_fast=ma_fast_val,
        ma_slow=ma_slow_val,
        bb_upper=bb_upper,
        bb_lower=bb_lower,
        volume_ok=volume_ok,
        price=price,
        reason=reason,
    )
    logger.debug("Analysis: %s | Price=%.4f | %s", signal.value, price, reason)
    return result
