from ..risk.sizing import sizing_for_profile
from ..utils.funding import funding_bps_estimate
from ..models.conformal import calibrate_threshold
from ..models.ensemble import Ensemble
import numpy as np

def generate_signals(features_df, labels_df, profile: str, fee_maker_bps: float, slippage_bps: float):
    # fit + predict
    ens = Ensemble().fit(features_df.Xb, features_df.y, features_df.Xs, features_df.y)
    probs = ens.predict_proba(features_df.Xb, features_df.Xs)[:,1]
    thr = calibrate_threshold(probs, features_df.y, target_hit=0.55)
    selected = np.where(probs >= thr)[0]
    signals = []
    for idx in selected:
        row = features_df.meta.iloc[idx]
        direction = row["dir"]  # LONG/SHORT determined by meta rules
        entry = row["entry"]
        sl = row["sl"]
        tps = [row["tp1"], row["tp2"], row["tp3"]]
        lev, risk, margin = sizing_for_profile(profile, entry, sl)
        funding_bps = funding_bps_estimate(row["symbol"])
        # expected_net obliczany w API przy publikacji — tu można również prefiltr
        signals.append(dict(symbol=row["symbol"], dir=direction, entry=entry, sl=sl, tp=tps,
                            lev=lev, risk=risk, margin_mode=margin, confidence=float(probs[idx])))
    return signals
