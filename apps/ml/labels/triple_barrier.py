import numpy as np
import pandas as pd

def apply_triple_barrier(df: pd.DataFrame, tp_pct: float, sl_pct: float, max_horizon: int):
    """
    Triple-barrier labeling.
    df must have: ['ts', 'c'] (timestamp ms, close)
    Returns DataFrame with ['label', 'horizon_ts', 'touched']
    """
    closes = df["c"].values
    ts = df["ts"].values
    labels, horizons, touched = [], [], []

    for i in range(len(closes)):
        start_price = closes[i]
        tp = start_price * (1 + tp_pct)
        sl = start_price * (1 - sl_pct)
        horizon_idx = min(i + max_horizon, len(closes) - 1)

        outcome = 0
        hit = "NONE"
        for j in range(i+1, horizon_idx+1):
            if closes[j] >= tp:
                outcome, hit = 1, "TP"
                horizon_idx = j
                break
            if closes[j] <= sl:
                outcome, hit = -1, "SL"
                horizon_idx = j
                break
        if outcome == 0:
            hit = "TIME"

        labels.append(outcome)
        horizons.append(ts[horizon_idx])
        touched.append(hit)

    df["label"] = labels
    df["horizon_ts"] = horizons
    df["touched"] = touched
    return df
