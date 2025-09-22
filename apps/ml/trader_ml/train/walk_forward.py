import pandas as pd
import numpy as np
from dataclasses import dataclass

@dataclass
class WFConfig:
    window_days: int = 60
    purge_bars: int = 60
    embargo_bars: int = 30

def split_walk_forward(df: pd.DataFrame, ts_col: str, cfg: WFConfig):
    df = df.sort_values(ts_col).reset_index(drop=True)
    start = 0
    results = []
    while True:
        train_end = start + int(cfg.window_days * 1440)  # zakładając 1m bars
        if train_end + cfg.purge_bars + cfg.embargo_bars >= len(df):
            break
        train_idx = np.arange(start, train_end)
        test_start = train_end + cfg.purge_bars
        test_end = min(len(df), test_start + int(cfg.window_days * 720))  # test ~30 dni (połowa)
        test_idx = np.arange(test_start, test_end)
        # embargo: „zanieczyszczone” obserwacje na końcu trenu wykluczone
        # (tu zrealizowane przez purge+shift okna)
        results.append((train_idx, test_idx))
        start += int(cfg.window_days * 480)
    return results
