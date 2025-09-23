# apps/ml/labeling.py
# PL: Etykietowanie triple-barrier (+ meta-label). Bez wycieków: patrzymy w przyszłość max K świec.
# EN: Triple-barrier labeling (+ meta-label). No leakage: only look ahead up to K bars.

from __future__ import annotations
import pandas as pd
import numpy as np

def triple_barrier_labels(df: pd.DataFrame,
                          tp_pct: float = 0.02,
                          sl_pct: float = 0.01,
                          max_horizon: int = 60,
                          price_col: str = "close") -> pd.DataFrame:
    """
    Returns columns:
      y:  1 if TP hit first, -1 if SL hit first, 0 if neither within horizon
      tp_hit, sl_hit: booleans
      tte: time-to-event (bars)
    """
    close = df[price_col].values
    n = len(df)
    y = np.zeros(n, dtype=int)
    tp_hit = np.zeros(n, dtype=bool)
    sl_hit = np.zeros(n, dtype=bool)
    tte = np.full(n, -1, dtype=int)

    for i in range(n):
        entry = close[i]
        if not np.isfinite(entry) or i == n - 1:
            continue
        up = entry * (1.0 + tp_pct)
        dn = entry * (1.0 - sl_pct)
        horizon = min(n - 1, i + max_horizon)
        # scan forward
        for j in range(i + 1, horizon + 1):
            c_hi = max(df["high"].iat[j], df["close"].iat[j])
            c_lo = min(df["low"].iat[j], df["close"].iat[j])
            if c_hi >= up:
                y[i] = 1
                tp_hit[i] = True
                tte[i] = j - i
                break
            if c_lo <= dn:
                y[i] = -1
                sl_hit[i] = True
                tte[i] = j - i
                break
        if tte[i] == -1:
            # no event
            y[i] = 0
            tte[i] = horizon - i
    out = df.copy()
    out["label_y"] = y
    out["label_tp_hit"] = tp_hit
    out["label_sl_hit"] = sl_hit
    out["label_tte"] = tte
    # Meta-label (simplest form: 1 if event (TP) happened, else 0; could be refined with base model proba)
    out["meta_label"] = (out["label_y"] == 1).astype(int)
    return out
