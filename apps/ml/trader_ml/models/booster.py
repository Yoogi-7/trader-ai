from lightgbm import LGBMClassifier

def make_booster():
    return LGBMClassifier(
        n_estimators=400, learning_rate=0.03, max_depth=-1, subsample=0.9, colsample_bytree=0.9,
        reg_alpha=0.1, reg_lambda=0.3, random_state=1337
    )
