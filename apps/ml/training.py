# apps/ml/training.py
# PL: Orkiestracja treningu/tuningu strategii: walk-forward z purge/embargo, backtest OOS, Optuna/random search.
# EN: Training/tuning orchestration: WF with purge/embargo, OOS backtest, Optuna/random search.

from __future__ import annotations
import os, json, random, time
from typing import Dict, Any, List, Tuple, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select
from apps.api.db import models
from apps.ml.walkforward import make_walkforward_indices
from apps.ml.backtest import backtest_signals, BTParams, load_bars
from apps.ml.registry import save_artifact

OPTUNA_N_TRIALS = int(os.getenv("OPTUNA_N_TRIALS", "50"))
WALK_FORWARD_PURGE = int(os.getenv("WALK_FORWARD_PURGE", "10"))
WALK_FORWARD_EMBARGO = int(os.getenv("WALK_FORWARD_EMBARGO", "5"))

def _get_signals_for_period(db: Session, symbol: str, tf: str, start_ts: int, end_ts: int) -> List[models.Signal]:
    q = select(models.Signal).where(
        models.Signal.symbol == symbol,
        models.Signal.tf_base == tf,
        models.Signal.ts >= start_ts,
        models.Signal.ts <= end_ts,
        models.Signal.status == "published",
    ).order_by(models.Signal.ts.asc())
    return list(db.execute(q).scalars().all())

def _search_space() -> Dict[str, Tuple[float,float]]:
    # prosty space pod strategię: lev, time-stop, slippage_bps (limit), funding_rate
    return {
        "desired_leverage": (2.0, 10.0),
        "time_stop_min": (60.0, 600.0),
        "slippage_bps": (2.0, 30.0),
        "funding_rate_hourly": (-0.00005, 0.00005),  # -5bps/h..+5bps/h
    }

def _sample_params() -> Dict[str, float]:
    sp = _search_space()
    return {k: random.uniform(v[0], v[1]) for k, v in sp.items()}

def _objective_random(
    db: Session, symbol: str, tf: str, bars: List[Dict[str, Any]], signals: List[models.Signal], capital: float, risk: str, n_trials: int
) -> Tuple[Dict[str, Any], Dict[str, float]]:
    best = None
    best_metrics: Dict[str, float] = {}
    for _ in range(max(1, n_trials)):
        hp = _sample_params()
        bt_params = BTParams(
            capital=capital,
            risk=risk,
            taker_only=True,
            funding_rate_hourly=hp["funding_rate_hourly"],
            slippage_bps=hp["slippage_bps"],
            time_stop_min=int(hp["time_stop_min"]),
        )
        trades, metrics = backtest_signals(db, symbol, tf, signals, bt_params, bars)
        score = metrics["hit_rate_tp1"]  # primary objective (target >= 0.55)
        if best is None or score > best_metrics.get("hit_rate_tp1", 0.0):
            best = hp
            best_metrics = metrics
    return best or _sample_params(), best_metrics

def _objective_optuna(
    db: Session, symbol: str, tf: str, bars: List[Dict[str, Any]], signals: List[models.Signal], capital: float, risk: str, n_trials: int
) -> Tuple[Dict[str, Any], Dict[str, float]]:
    import optuna  # type: ignore
    def objective(trial: "optuna.trial.Trial"):
        hp = {
            "desired_leverage": trial.suggest_float("desired_leverage", 2.0, 10.0),
            "time_stop_min": trial.suggest_int("time_stop_min", 60, 600),
            "slippage_bps": trial.suggest_float("slippage_bps", 2.0, 30.0),
            "funding_rate_hourly": trial.suggest_float("funding_rate_hourly", -0.00005, 0.00005),
        }
        bt_params = BTParams(
            capital=capital,
            risk=risk,
            taker_only=True,
            funding_rate_hourly=hp["funding_rate_hourly"],
            slippage_bps=hp["slippage_bps"],
            time_stop_min=int(hp["time_stop_min"]),
        )
        _, metrics = backtest_signals(db, symbol, tf, signals, bt_params, bars)
        # max hit-rate TP1; tie-break by MAR
        trial.set_user_attr("metrics", metrics)
        return metrics["hit_rate_tp1"]
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials)
    hp = study.best_trial.params
    metrics = study.best_trial.user_attrs["metrics"]
    return hp, metrics

def walkforward_tune_and_backtest(
    db: Session,
    symbol: str,
    tf: str,
    start_ts: int,
    end_ts: int,
    n_folds: int,
    capital: float,
    risk: str,
) -> Dict[str, Any]:
    # Załaduj wykres do backtestu (dla wyjść)
    bars_all = load_bars(db, symbol, tf, start_ts, end_ts)
    if not bars_all:
        return {"ok": False, "reason": "no_bars"}

    ts_list = [b["ts"] for b in bars_all]
    n = len(ts_list)

    folds = make_walkforward_indices(n=n, n_folds=n_folds, purge=WALK_FORWARD_PURGE, embargo=WALK_FORWARD_EMBARGO)
    oos_metrics: List[Dict[str, float]] = []
    best_params: Optional[Dict[str, Any]] = None

    for f in folds:
        tr_start, tr_end = ts_list[f.train_idx[0]], ts_list[f.train_idx[1]]
        te_start, te_end = ts_list[f.test_idx[0]], ts_list[f.test_idx[1]]

        # pobierz sygnały tylko w obrębie danych (na razie zakładamy, że sygnały już istnieją w DB)
        tr_signals = _get_signals_for_period(db, symbol, tf, tr_start, tr_end)
        te_signals = _get_signals_for_period(db, symbol, tf, te_start, te_end)

        # dane do symulacji
        tr_bars = [b for b in bars_all if tr_start <= b["ts"] <= tr_end]
        te_bars = [b for b in bars_all if te_start <= b["ts"] <= te_end]

        # tuning (Optuna -> fallback random)
        try:
            hp, _ = _objective_optuna(db, symbol, tf, tr_bars, tr_signals, capital, risk, OPTUNA_N_TRIALS)
        except Exception:
            hp, _ = _objective_random(db, symbol, tf, tr_bars, tr_signals, capital, risk, OPTUNA_N_TRIALS)

        # OOS backtest
        bt_params = BTParams(
            capital=capital,
            risk=risk,
            taker_only=True,
            funding_rate_hourly=hp.get("funding_rate_hourly", 0.0),
            slippage_bps=hp.get("slippage_bps", 10.0),
            time_stop_min=int(hp.get("time_stop_min", 240)),
        )
        _, metrics = backtest_signals(db, symbol, tf, te_signals, bt_params, te_bars)
        oos_metrics.append(metrics)
        best_params = hp

    # agregacja metryk OOS
    if not oos_metrics:
        return {"ok": False, "reason": "no_oos_metrics"}

    def avg(key: str) -> float:
        return float(sum(m.get(key, 0.0) for m in oos_metrics) / max(1, len(oos_metrics)))

    summary = {
        "ok": True,
        "symbol": symbol,
        "tf": tf,
        "folds": len(oos_metrics),
        "metrics_avg": {
            "hit_rate_tp1": avg("hit_rate_tp1"),
            "hit_rate_tp2": avg("hit_rate_tp2"),
            "hit_rate_tp3": avg("hit_rate_tp3"),
            "pf": avg("pf"),
            "mar": avg("mar"),
            "max_dd_pct": avg("max_dd_pct"),
            "trades": avg("trades"),
        },
        "best_params": best_params or {},
    }
    return summary

def save_training_result(db: Session, run_id: int, summary: Dict[str, Any]) -> None:
    tr = db.get(models.TrainingRun, run_id)
    if tr:
        tr.finished_at = int(time.time()*1000)
        tr.status = "done" if summary.get("ok") else "error"
        tr.metrics_json = summary
        db.commit()

def save_backtest_result(db: Session, bt_id: int, summary: Dict[str, Any], trades: List[Dict[str, Any]] | None = None) -> None:
    bt = db.get(models.Backtest, bt_id)
    if bt:
        bt.finished_at = int(time.time()*1000)
        bt.summary_json = summary
        db.commit()
