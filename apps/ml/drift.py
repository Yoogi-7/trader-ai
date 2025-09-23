# apps/ml/drift.py
from __future__ import annotations
import numpy as np
from typing import Tuple
try:
    from scipy.stats import ks_2samp
except Exception:
    ks_2samp = None

def _hist(a: np.ndarray, bins: int = 10) -> Tuple[np.ndarray, np.ndarray]:
    a = a[~np.isnan(a)]
    if a.size == 0:
        return np.zeros(bins), np.linspace(0, 1, bins + 1)
    h, e = np.histogram(a, bins=bins)
    return h.astype(float), e

def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    eh, edges = _hist(expected, bins)
    ah, _ = np.histogram(actual[~np.isnan(actual)], bins=edges)
    ah = ah.astype(float)
    e = eh / (eh.sum() + 1e-12)
    a = ah / (ah.sum() + 1e-12)
    e = np.clip(e, 1e-6, None)
    a = np.clip(a, 1e-6, None)
    return float(np.sum((a - e) * np.log(a / e)))

def ks(expected: np.ndarray, actual: np.ndarray) -> float:
    if ks_2samp is None:
        # fallback: mediana
        return float(abs(np.nanmedian(expected) - np.nanmedian(actual)))
    res = ks_2samp(expected[~np.isnan(expected)], actual[~np.isnan(actual)])
    return float(res.statistic)
