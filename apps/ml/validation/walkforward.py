from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import Iterator, Tuple

@dataclass
class PurgedEmbargoSplit:
    n_splits: int = 5
    embargo: int = 10  # liczba próbek na końcu train, które wykluczamy z testu

    def split(self, X, timestamps: np.ndarray) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        """
        Zakładamy rosnące timestamps (int ms). Dzielimy na równe bloki czasowe.
        W każdym kroku: train = bloki [0..i], test = blok i+1, z purge+embargo.
        """
        n = len(X)
        order = np.argsort(timestamps)
        X_idx = order  # już posortowane
        folds = np.array_split(X_idx, self.n_splits + 1)

        for i in range(self.n_splits):
            train_idx = np.concatenate(folds[:i+1]) if i >= 0 else np.array([], dtype=int)
            test_idx = folds[i+1]

            # Purge & Embargo – wytnij z train końcowe 'embargo' obserwacji
            if self.embargo > 0 and len(train_idx) > self.embargo:
                train_idx = train_idx[:-self.embargo]

            yield np.sort(train_idx), np.sort(test_idx)
