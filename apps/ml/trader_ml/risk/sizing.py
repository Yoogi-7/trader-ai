def sizing_for_profile(profile: str, entry: float, sl: float):
    p = profile.upper()
    if p == "LOW":
        return 5.0, 0.005, "ISOLATED"
    if p == "MED":
        return 10.0, 0.01, "ISOLATED"
    return 20.0, 0.02, "CROSS"
