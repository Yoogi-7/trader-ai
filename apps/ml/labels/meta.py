import pandas as pd

def meta_label(base_preds: pd.Series, labels: pd.Series) -> pd.Series:
    """
    Meta-labeling: only keep trades where base model was correct.
    base_preds: model predictions (1/-1)
    labels: true labels from triple-barrier
    Returns: 1 if base was correct, 0 otherwise
    """
    return (base_preds * labels > 0).astype(int)
