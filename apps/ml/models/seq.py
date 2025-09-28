# apps/ml/models/seq.py
from __future__ import annotations
import numpy as np
from typing import Dict, Any

class SeqModel:
    """
    Lightweight 1D Conv (TCN-ish) with numpy fallback.
    """
    def __init__(self, params: Dict[str, Any] | None = None):
        self.params = params or {}
        self.backend = None
        self.model = None  # (PyTorch) or (weights tuple) for fallback

    def fit(self, X: np.ndarray, y: np.ndarray):
        # X: (n, t, f)  y: (n,)
        try:
            import torch, torch.nn as nn, torch.optim as optim  # type: ignore
            class Net(nn.Module):
                def __init__(self, in_ch: int):
                    super().__init__()
                    self.conv1 = nn.Conv1d(in_ch, 16, kernel_size=3, padding=1)
                    self.conv2 = nn.Conv1d(16, 16, kernel_size=3, padding=1)
                    self.head = nn.Linear(16, 1)
                    self.act = nn.ReLU()
                def forward(self, x):  # x: (b,t,f)
                    x = x.transpose(1,2)  # (b,f,t)
                    x = self.act(self.conv1(x))
                    x = self.act(self.conv2(x))
                    x = x.mean(dim=2)
                    x = self.head(x)
                    return x.squeeze(-1)
            device = 'cpu'
            Xt = torch.tensor(X, dtype=torch.float32, device=device)
            yt = torch.tensor(y, dtype=torch.float32, device=device)
            net = Net(X.shape[-1]).to(device)
            opt = optim.Adam(net.parameters(), lr=1e-3)
            loss = nn.BCEWithLogitsLoss()
            net.train()
            for _ in range(50):
                opt.zero_grad()
                o = net(Xt)
                l = loss(o, yt)
                l.backward(); opt.step()
            self.model = net.eval()
            self.backend = "torch"
            return
        except Exception:
            pass
        # numpy fallback: logistic on simple mean features
        from sklearn.linear_model import LogisticRegression  # type: ignore
        X2 = X.mean(axis=1)
        clf = LogisticRegression(max_iter=500)
        clf.fit(X2, y)
        self.model = clf
        self.backend = "sklearn"

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.backend == "torch":
            import torch  # type: ignore
            with torch.no_grad():
                Xt = torch.tensor(X, dtype=torch.float32)
                o = self.model(Xt).numpy()
            p1 = 1 / (1 + np.exp(-o))
            return np.vstack([1 - p1, p1]).T
        # sklearn fallback
        X2 = X.mean(axis=1)
        p1 = self.model.predict_proba(X2)[:, 1]
        return np.vstack([1 - p1, p1]).T
