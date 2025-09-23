# apps/ml/walkforward.py
# PL: Podziały walk-forward z purge i embargo.
# EN: Walk-forward splits with purge & embargo.

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class Fold:
    train_idx: Tuple[int, int]
    test_idx: Tuple[int, int]

def make_walkforward_indices(n: int, n_folds: int, purge: int, embargo: int) -> List[Fold]:
    """
    n: total number of samples ordered by time (0..n-1)
    n_folds: number of WF folds
    purge: number of samples to purge between train end and test start
    embargo: number of samples to drop after test end (to avoid leakage to next train)
    """
    assert n_folds >= 2, "n_folds must be >=2"
    fold_size = n // n_folds
    folds: List[Fold] = []
    for i in range(n_folds - 1):
        train_end = fold_size * (i + 1) - 1
        test_start = train_end + 1 + purge
        test_end = min(fold_size * (i + 2) - 1, n - 1)
        if test_start >= n or test_start > test_end:
            break
        train_start = 0
        # embargo affects next train (not this function directly), caller can enforce when stitching
        folds.append(Fold(train_idx=(train_start, train_end), test_idx=(test_start, test_end)))
    return folds
