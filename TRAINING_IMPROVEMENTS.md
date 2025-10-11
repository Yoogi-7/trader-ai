# Training Quality Improvements - Implementation Summary

**Date**: 2025-10-08
**Status**: ✅ All phases completed

---

## 🎯 Problems Identified

### 1. **Critical: ETH Low Recall (5-15%)**
- Model too conservative, missing most profitable opportunities
- Class imbalance not handled properly

### 2. **Suboptimal Hyperparameters**
- Too much regularization (reg_alpha/lambda = 0.1/1.0)
- Small model capacity (num_leaves = 63)
- No class weight balancing

### 3. **Conservative Labels**
- TP multiplier only 2.0x ATR (too tight)
- Not aligned with signal engine TP2/TP3

### 4. **Missing Features**
- No rolling statistics
- No momentum features
- No z-score normalization

---

## ✅ Implemented Solutions

### **Phase 1: Class Imbalance Handling** ✅

#### File: `apps/ml/models.py`

**Changes**:
1. Added `is_unbalance: True` to LightGBM
2. Added `scale_pos_weight: 2.0` to both LGBM and XGBoost
3. Lowered prediction threshold from 0.5 → **0.35**

```python
# Before
'num_leaves': 63,
'learning_rate': 0.03,
# No class balancing

# After
'num_leaves': 127,  # +100% capacity
'learning_rate': 0.02,  # More stable
'is_unbalance': True,  # Handle imbalance
'scale_pos_weight': 2.0,  # 2x weight for LONG signals
```

**Expected Impact**: +300-400% recall improvement for ETH

---

### **Phase 2: Hyperparameter Optimization** ✅

#### Updated Parameters:

| Parameter | Before | After | Reason |
|-----------|--------|-------|--------|
| `num_leaves` | 63 | **127** | More complex patterns |
| `learning_rate` | 0.03 | **0.02** | More stable training |
| `feature_fraction` | 0.8 | **0.85** | Use more features |
| `bagging_fraction` | 0.8 | **0.85** | More diversity |
| `min_child_samples` | 20 | **15** | More flexibility |
| `reg_alpha` | 0.1 | **0.05** | Less L1 regularization |
| `reg_lambda` | 0.1/1.0 | **0.05/0.5** | Less L2 regularization |
| `max_depth` | -1/8 | **10** | Better generalization |
| `num_boost_round` | 15000 | **20000** | More training rounds |
| `early_stopping` | 500 | **800** | More patience |

**New Features**:
- Added `tree_method: 'hist'` for faster training
- Added `find_optimal_threshold()` method for F1 optimization

**Expected Impact**: +5-10% accuracy improvement

---

### **Phase 3: Label Quality Improvement** ✅

#### File: `apps/ml/training.py`

**Changes**:
```python
# Before
tp_atr_multiplier=2.0  # Too conservative

# After
tp_atr_multiplier=3.5  # Aligned with TP2 in signal_engine
```

**Fold Reduction** (faster iteration):
```python
test_period_days=21  # Reduced from 30
min_train_days=120   # Reduced from 180
```

**Expected Impact**:
- Labels aligned with actual signal engine targets
- ~40% faster training (45-50 folds instead of 65-67)
- Training time: 60-70h → **35-45h**

---

### **Phase 4: Feature Engineering** ✅

#### File: `apps/ml/features.py`

**New Features Added** (17 total):

1. **Price Statistics**:
   - `close_rolling_mean_20`
   - `close_rolling_std_20`
   - `close_zscore`

2. **Volume Statistics**:
   - `volume_rolling_mean_20`
   - `volume_rolling_std_20`
   - `volume_zscore`

3. **Momentum Features**:
   - `price_momentum_5/10/20`
   - `volume_momentum_5/10`

4. **Correlation**:
   - `price_volume_corr`

5. **Range Statistics**:
   - `hl_range`
   - `hl_range_ma`
   - `hl_range_std`

**Expected Impact**: Better trend detection, +3-5% accuracy

---

### **Phase 5: Sample Weighting** ✅

#### File: `apps/ml/models.py`

**Changes**:
```python
def train(self, X_train, y_train, X_val, y_val, sample_weights=None):
    # Apply recency weights (recent data gets higher weight)
    if sample_weights is None:
        sample_weights = np.linspace(0.5, 1.0, len(X_train))
```

**Effect**: Recent market conditions weighted 2x more than older data

---

## 📊 Expected Performance Improvements

### **Before vs After**:

| Metric | ETH (Before) | ETH (Target) | Improvement |
|--------|--------------|--------------|-------------|
| **Recall** | 5-15% | 40-60% | **+300-400%** |
| **Accuracy** | 67.7% | 68-70% | +2-3% |
| **ROC AUC** | 63.8% | 66-68% | +3-5% |

| Metric | BTC (Before) | BTC (Target) | Improvement |
|--------|--------------|--------------|-------------|
| **Accuracy** | 58.9% | 62-65% | **+5-10%** |
| **ROC AUC** | 58.8% | 62-65% | **+5-10%** |

| Metric | BNB (Before) | BNB (Target) | Improvement |
|--------|--------------|--------------|-------------|
| **Accuracy** | 59.5% | 62-64% | **+4-7%** |
| **ROC AUC** | 61.8% | 65-68% | **+5-10%** |

### **Training Efficiency**:
- **Folds**: 65-67 → **~45** (-30%)
- **Time per symbol**: 60-70h → **35-45h** (-40%)
- **Total time for 3 symbols**: 180-210h → **105-135h**

---

## 🚀 Next Steps

### **Immediate (to apply changes)**:

1. **Stop current training jobs**:
   ```bash
   docker exec traderai-db psql -U traderai -d traderai -c "UPDATE training_jobs SET status = 'cancelled' WHERE status = 'training';"
   ```

2. **Restart training workers** (to load new code):
   ```bash
   docker restart traderai-worker-training2 traderai-worker-training3 traderai-worker
   ```

3. **Start new training** with improved parameters:
   ```bash
   # Will automatically use new hyperparameters
   curl -X POST http://localhost:8000/api/training/start \
     -H "Content-Type: application/json" \
     -d '{"symbol": "BTC/USDT", "timeframe": "M15"}'
   ```

### **Monitoring**:

Monitor fold metrics to verify improvements:
```bash
# Check fold metrics
docker logs traderai-worker-training2 -f | grep "OOS Test Metrics"

# Expected to see:
# - Recall > 30% (up from 5-15%)
# - Accuracy similar or better
# - F1 score improved
```

### **Optional Enhancements** (future):

1. **Add focal loss** for even better class imbalance handling
2. **Implement Optuna** for hyperparameter tuning
3. **Add volatility-adaptive labeling** (dynamic TP/SL based on regime)
4. **Create fold metrics table** for better tracking

---

## 📝 Files Modified

| File | Changes | Status |
|------|---------|--------|
| `apps/ml/models.py` | Hyperparameters, class balancing, threshold, sample weights | ✅ |
| `apps/ml/training.py` | TP multiplier, fold reduction | ✅ |
| `apps/ml/features.py` | Rolling stats, momentum features | ✅ |

---

## ⚠️ Important Notes

1. **Backward Compatibility**: Old models will continue to work with default threshold 0.5
2. **New models** will automatically use threshold 0.35
3. **Retraining Required**: Current jobs should be cancelled and restarted
4. **Feature Count**: Increased from ~80 to ~97 features (+21%)

---

## 🎓 Key Learnings

1. **Class Imbalance is Critical**: Without proper handling, model becomes too conservative
2. **Threshold Matters**: Default 0.5 is not optimal for imbalanced crypto data
3. **Label Quality**: TP targets must align with actual trading strategy
4. **Regularization Balance**: Too much regularization hurts crypto volatility modeling
5. **Recency Bias**: Recent market conditions more relevant than old data

---

## 📊 Validation Plan

After retraining completes, validate improvements:

1. **Check Recall**: Should be 40-60% (up from 5-15%)
2. **Monitor F1 Score**: Should improve significantly
3. **Verify Precision**: Should not drop below 45%
4. **Compare ROC AUC**: Should increase 3-5%
5. **Backtest on OOS data**: Ensure improvements generalize

---

**Status**: ✅ **All improvements implemented and ready for deployment**

**Estimated Improvement Timeline**: 35-45 hours (new training cycle)
