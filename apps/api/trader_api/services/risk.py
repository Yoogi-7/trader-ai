def profile_params(profile: str):
    p = profile.upper()
    if p == "LOW":
        return dict(risk_per_trade=0.005, max_lev=5, max_parallel=3, margin="ISOLATED")
    if p == "MED":
        return dict(risk_per_trade=0.01, max_lev=10, max_parallel=5, margin="ISOLATED")
    return dict(risk_per_trade=0.02, max_lev=20, max_parallel=7, margin="CROSS")
