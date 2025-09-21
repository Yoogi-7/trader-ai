# Simple TA features (EMA/RSI-like) for demo
import numpy as np
import pandas as pd

def ema(series: pd.Series, span=14):
    return series.ewm(span=span, adjust=False).mean()

def rsi(series: pd.Series, period=14):
    delta = series.diff()
    up = (delta.clip(lower=0)).rolling(period).mean()
    down = (-delta.clip(upper=0)).rolling(period).mean()
    rs = up / (down + 1e-9)
    return 100 - (100 / (1 + rs))

def basic_features(df: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame(index=df.index)
    f["ema_fast"] = ema(df["c"], 12)
    f["ema_slow"] = ema(df["c"], 26)
    f["rsi14"] = rsi(df["c"], 14)
    f["atr"] = (df["h"] - df["l"]).rolling(14).mean()
    f = f.fillna(method="bfill").fillna(method="ffill")
    return f