# apps/ml/ta_utils.py
# PL: Narzędzia TA liczone na DataFrame OHLCV (pandas), bez zewnętrznych zależności TA-lib.
# EN: TA utilities computed on OHLCV pandas DataFrame, no TA-lib dependency.

from __future__ import annotations
import numpy as np
import pandas as pd

def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()

def ema(df: pd.DataFrame, period: int, col: str = "close", out: str | None = None) -> pd.DataFrame:
    out = out or f"ema_{period}"
    df[out] = _ema(df[col], period)
    return df

def rsi(df: pd.DataFrame, period: int = 14, col: str = "close", out: str = "rsi") -> pd.DataFrame:
    delta = df[col].diff()
    up = np.where(delta > 0, delta, 0.0)
    down = np.where(delta < 0, -delta, 0.0)
    roll_up = pd.Series(up, index=df.index).ewm(alpha=1/period, adjust=False).mean()
    roll_down = pd.Series(down, index=df.index).ewm(alpha=1/period, adjust=False).mean()
    rs = roll_up / (roll_down.replace(0, np.nan))
    df[out] = 100.0 - (100.0 / (1.0 + rs))
    df[out] = df[out].fillna(0.0)
    return df

def stoch(df: pd.DataFrame, k_period: int = 14, d_period: int = 3, out_k: str = "stoch_k", out_d: str = "stoch_d") -> pd.DataFrame:
    low_min = df["low"].rolling(k_period, min_periods=k_period).min()
    high_max = df["high"].rolling(k_period, min_periods=k_period).max()
    k = (df["close"] - low_min) / (high_max - low_min + 1e-12) * 100.0
    d = k.rolling(d_period, min_periods=d_period).mean()
    df[out_k] = k.fillna(0.0)
    df[out_d] = d.fillna(0.0)
    return df

def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, col: str = "close",
         out_macd: str = "macd", out_signal: str = "macd_signal", out_hist: str = "macd_hist") -> pd.DataFrame:
    ema_fast = _ema(df[col], fast)
    ema_slow = _ema(df[col], slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    df[out_macd] = macd_line
    df[out_signal] = signal_line
    df[out_hist] = macd_line - signal_line
    return df

def atr(df: pd.DataFrame, period: int = 14, out: str = "atr") -> pd.DataFrame:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df[out] = tr.rolling(period, min_periods=period).mean()
    return df

def bollinger(df: pd.DataFrame, period: int = 20, n_std: float = 2.0,
              out_mid: str = "bb_mid", out_up: str = "bb_up", out_low: str = "bb_low") -> pd.DataFrame:
    mid = df["close"].rolling(period, min_periods=period).mean()
    std = df["close"].rolling(period, min_periods=period).std(ddof=0)
    df[out_mid] = mid
    df[out_up] = mid + n_std * std
    df[out_low] = mid - n_std * std
    return df

def ichimoku(df: pd.DataFrame, conv_period: int = 9, base_period: int = 26, span_b_period: int = 52,
             out_conv: str = "ichi_conv", out_base: str = "ichi_base",
             out_span_a: str = "ichi_span_a", out_span_b: str = "ichi_span_b") -> pd.DataFrame:
    conv = (df["high"].rolling(conv_period).max() + df["low"].rolling(conv_period).min()) / 2.0
    base = (df["high"].rolling(base_period).max() + df["low"].rolling(base_period).min()) / 2.0
    span_a = (conv + base) / 2.0
    span_b = (df["high"].rolling(span_b_period).max() + df["low"].rolling(span_b_period).min()) / 2.0
    df[out_conv] = conv
    df[out_base] = base
    df[out_span_a] = span_a.shift(base_period)  # projected forward; we keep shifted as-is for reference
    df[out_span_b] = span_b.shift(base_period)
    return df

def pivot_points(df: pd.DataFrame, out_p: str = "pp", out_r1: str = "pp_r1", out_s1: str = "pp_s1",
                 out_r2: str = "pp_r2", out_s2: str = "pp_s2") -> pd.DataFrame:
    # Classic PP computed per-candle on previous candle (rolling variant)
    p = (df["high"].shift() + df["low"].shift() + df["close"].shift()) / 3.0
    r1 = 2 * p - df["low"].shift()
    s1 = 2 * p - df["high"].shift()
    r2 = p + (df["high"].shift() - df["low"].shift())
    s2 = p - (df["high"].shift() - df["low"].shift())
    df[out_p] = p
    df[out_r1] = r1
    df[out_s1] = s1
    df[out_r2] = r2
    df[out_s2] = s2
    return df

def fibonacci_levels(df: pd.DataFrame, lookback: int = 120,
                     out_prefix: str = "fibo") -> pd.DataFrame:
    # Swing high/low in a rolling window; compute common fib retracement levels
    hh = df["high"].rolling(lookback, min_periods=lookback).max()
    ll = df["low"].rolling(lookback, min_periods=lookback).min()
    rng = (hh - ll).replace(0, np.nan)
    for lvl, name in [(0.236, "236"), (0.382, "382"), (0.5, "500"), (0.618, "618"), (0.786, "786")]:
        df[f"{out_prefix}_{name}"] = hh - lvl * rng
    return df

def realized_vol(df: pd.DataFrame, period: int = 30, out: str = "rv") -> pd.DataFrame:
    ret = np.log(df["close"]).diff()
    df[out] = (ret.rolling(period).std(ddof=0) * np.sqrt(1440))  # annualized-ish for 1m; generic scaling
    return df

def microstructure(df: pd.DataFrame,
                   out_spr_rel: str = "ms_spread_rel",
                   out_vol_imb: str = "ms_vol_imb") -> pd.DataFrame:
    # Approximation (no L2 depth): relative spread = (H-L)/C; volume imbalance = up-volume - down-volume proxy
    df[out_spr_rel] = (df["high"] - df["low"]) / (df["close"] + 1e-12)
    up_vol = df.apply(lambda r: r["volume"] if r["close"] >= r["open"] else 0.0, axis=1)
    dn_vol = df.apply(lambda r: r["volume"] if r["close"] < r["open"] else 0.0, axis=1)
    denom = (up_vol + dn_vol).replace(0, np.nan)
    df[out_vol_imb] = (up_vol - dn_vol) / denom
    df[out_vol_imb] = df[out_vol_imb].fillna(0.0)
    return df

def adx_regime(df: pd.DataFrame, period: int = 14, out: str = "regime") -> pd.DataFrame:
    # Simple regime detection via ADX & slope: trend(1), sideways(0), volatile(-1)
    # Compute ADX-like proxy (no TA-lib): based on directional movement and TR
    up_move = df["high"].diff()
    down_move = -df["low"].diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = pd.concat([(df["high"] - df["low"]),
                    (df["high"] - df["close"].shift()).abs(),
                    (df["low"] - df["close"].shift()).abs()], axis=1).max(axis=1)
    atr_p = tr.rolling(period, min_periods=period).mean()
    pdi = 100 * pd.Series(plus_dm, index=df.index).rolling(period, min_periods=period).sum() / (atr_p * period + 1e-12)
    mdi = 100 * pd.Series(minus_dm, index=df.index).rolling(period, min_periods=period).sum() / (atr_p * period + 1e-12)
    dx = (abs(pdi - mdi) / (pdi + mdi + 1e-12)) * 100
    adx = dx.rolling(period, min_periods=period).mean()
    slope = df["close"].pct_change(periods=period)
    regime = np.where(adx > 20, 1, 0)  # trend if ADX>20
    regime = np.where((adx <= 20) & (df["rv"].fillna(0) > df["rv"].rolling(period, min_periods=period).mean().fillna(0)), -1, regime)
    df[out] = regime
    return df
