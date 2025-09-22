# uproszczony „sequence” -> tu użyjemy gradient boosting na oknach cech jako proxy
from xgboost import XGBClassifier

def make_sequence():
    return XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05, subsample=0.9, colsample_bytree=0.9, random_state=1337
    )
