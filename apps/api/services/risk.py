
from apps.api.config import get_settings

def map_profile(profile: str) -> dict:
    s = get_settings()
    profile = profile.upper()
    if profile == "LOW":
        return {"risk_pct": s.RISK_PCT_LOW, "max_parallel": s.MAX_PARALLEL_LOW, "max_lev": s.MAX_LEV_LOW}
    if profile == "MED":
        return {"risk_pct": s.RISK_PCT_MED, "max_parallel": s.MAX_PARALLEL_MED, "max_lev": s.MAX_LEV_MED}
    return {"risk_pct": s.RISK_PCT_HIGH, "max_parallel": s.MAX_PARALLEL_HIGH, "max_lev": s.MAX_LEV_HIGH}
