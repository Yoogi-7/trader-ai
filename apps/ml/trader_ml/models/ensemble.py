from .booster import make_booster
from .sequence import make_sequence
import numpy as np

class Ensemble:
    def __init__(self):
        self.boost = make_booster()
        self.seq = make_sequence()

    def fit(self, Xb, yb, Xs, ys):
        self.boost.fit(Xb, yb)
        self.seq.fit(Xs, ys)
        return self

    def predict_proba(self, Xb, Xs):
        pb = self.boost.predict_proba(Xb)[:,1]
        ps = self.seq.predict_proba(Xs)[:,1]
        # simple stacking: mean
        p = (pb + ps) / 2.0
        return np.vstack([1-p, p]).T
