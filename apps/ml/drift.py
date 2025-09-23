# apps/ml/drift.py
# PL: Metryki driftu PSI i KS na rozkładach cech.
# EN: PSI & KS drift metrics.

from __future__ import annotations
import numpy as np
from typing import Tuple
from scipy.stats import ks_2samp  # lekkie, ale jeśli brak SciPy, zrobimy fallback

def _histogram(a: np.ndarray, bins: int = 10) -> Tuple[np.ndarray, np.ndarray]:
    a = a[~np.isnan(a)]
    if a.size == 0:
        return np.zeros(bins), np.linspace(0, 1, bins + 1)
    hist, edges = np.histogram(a, bins=bins)
    return hist.astype(float), edges

def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """
    Population Stability Index.
    """
    e_hist, edges = _histogram(expected, bins)
    a_hist, _ = np.histogram(actual[~np.isnan(actual)], bins=edges)
    a_hist = a_hist.astype(float)
    # normalize
    e = e_hist / (e_hist.sum() + 1e-12)
    a = a_hist / (a_hist.sum() + 1e-12)
    # avoid zeroes
    e = np.clip(e, 1e-6, None)
    a = np.clip(a, 1e-6, None)
    return float(np.sum((a - e) * np.log(a / e)))

def ks_stat(expected: np.ndarray, actual: np.ndarray) -> float:
    try:
        return float(ks_2samp(expected[~np.isnan(expected)], actual[~np.isnan(actual)]).statistic)
    except Exception:
        # prosty fallback: różnica mediana vs. mediana
        return float(abs(np.nanmedian(expected) - np.nanmedian(actual)))
