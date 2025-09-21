from __future__ import annotations
import json, os
import numpy as np
import pandas as pd
from typing import Dict, Any
from sqlalchemy.orm import Session
from apps.api.db import SessionLocal
from apps.api.models import TrainingRun, Feature
from apps.ml.validation.walkforward import PurgedEmbargoSplit
import lightgbm as lgb
import optuna
from sklearn.metrics import roc_auc_score, accuracy_score

def _load_features(db: Session, symbol: str, tf: str, version: str = "v1") -> pd.DataFrame:
    rows = db.query(Feature).filter(Feature.symbol==symbol, Feature.tf==tf, Feature.version==version).order_by(Feature.tstz.asc()).all()
    if not rows:
        raise RuntimeError("Brak features dla treningu.")
    # f_vector ma np. {"x1":..,"x2":..,"label":0/1}
    recs = []
    for r in rows:
        fv = dict(r.f_vector)
        fv["ts"] = r.ts
        recs.append(fv)
    df = pd.DataFrame(recs).dropna()
    return df

def _walkforward_score(df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
    y = df["label"].astype(int).values
    X = df.drop(columns=["label"]).drop(columns=["ts"]).values
    ts = df["ts"].values

    splitter = PurgedEmbargoSplit(n_splits=5, embargo=10)
    oos_preds = []
    oos_true  = []
    for tr_idx, te_idx in splitter.split(X, ts):
        if len(tr_idx) < 100 or len(te_idx) < 50:
            continue
        dtrain = lgb.Dataset(X[tr_idx], label=y[tr_idx])
        model = lgb.train(
            params={**params, "objective":"binary", "verbosity":-1},
            train_set=dtrain,
            num_boost_round=300
        )
        pred = model.predict(X[te_idx])
        oos_preds.append(pred); oos_true.append(y[te_idx])

    if not oos_preds:
        return {"oos_auc": 0.5, "oos_acc": 0.5}

    y_pred = np.concatenate(oos_preds)
    y_true = np.concatenate(oos_true)
    auc = float(roc_auc_score(y_true, y_pred))
    acc = float(accuracy_score(y_true, (y_pred>0.5).astype(int)))
    return {"oos_auc": auc, "oos_acc": acc}

def _objective(trial: optuna.Trial, df: pd.DataFrame):
    params = {
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "num_leaves": trial.suggest_int("num_leaves", 16, 256, log=True),
        "feature_fraction": trial.suggest_float("feature_fraction", 0.6, 1.0),
        "bagging_fraction": trial.suggest_float("bagging_fraction", 0.6, 1.0),
        "bagging_freq": trial.suggest_int("bagging_freq", 0, 5),
        "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 10, 200),
        "lambda_l1": trial.suggest_float("lambda_l1", 1e-8, 10.0, log=True),
        "lambda_l2": trial.suggest_float("lambda_l2", 1e-8, 10.0, log=True),
    }
    metrics = _walkforward_score(df, params)
    # Maksymalizujemy AUC OOS
    trial.set_user_attr("metrics", metrics)
    return metrics["oos_auc"]

def run(symbol: str = "BTCUSDT", tf: str = "15m", version: str = "v1", n_trials: int = 20) -> Dict[str, Any]:
    db: Session = SessionLocal()
    tr = TrainingRun(status="running", params_json={"symbol":symbol,"tf":tf,"n_trials":n_trials}, metrics_json={})
    db.add(tr); db.commit()

    try:
        df = _load_features(db, symbol=symbol, tf=tf, version=version)
        study = optuna.create_study(direction="maximize")
        study.optimize(lambda t: _objective(t, df), n_trials=n_trials)

        best = study.best_trial.user_attrs["metrics"]
        db_tr = db.query(TrainingRun).get(tr.id)
        db_tr.status = "done"
        db_tr.metrics_json = {"best_oos_auc": best["oos_auc"], "best_oos_acc": best["oos_acc"]}
        db.commit()
        return db_tr.metrics_json
    except Exception as e:
        db_tr = db.query(TrainingRun).get(tr.id)
        db_tr.status = "error"
        db_tr.metrics_json = {"error": str(e)}
        db.commit()
        return db_tr.metrics_json
    finally:
        db.close()

if __name__ == "__main__":
    print(run())
