# Walk-Forward Validation Pipeline

Complete ML training pipeline with walk-forward validation using expanding windows, preventing data leakage and overfitting.

## 🎯 Key Features

### 1. **Walk-Forward Validation with Expanding Windows**
- Training on **all historical data** (expanding window approach)
- Out-of-sample validation on future periods
- Purge & Embargo to eliminate data leakage
- Metrics aggregation across multiple splits

### 2. **Model Registry**
- Model versioning (v1, v2, v3...)
- Metrics tracking for each version
- Deployment to different environments (production/staging)
- Rollback to previous versions
- Model version comparison

### 3. **Performance Tracking**
- Real-time performance monitoring
- Performance degradation detection
- Automated performance reports
- Model comparison

### 4. **Ensemble Models**
- LightGBM + XGBoost ensemble
- Conformal Prediction for confidence calibration
- Feature importance analysis

## 📁 Project Structure

```
apps/ml/
├── training.py              # Main walk-forward pipeline
├── walkforward.py           # Walk-forward validator
├── models.py                # Ensemble models (LightGBM + XGBoost)
├── features.py              # Feature engineering
├── labeling.py              # Triple barrier labeling
├── model_registry.py        # Model versioning & registry
└── performance_tracker.py   # Performance monitoring

apps/api/routers/
└── train.py                 # API endpoints

examples/
└── walkforward_example.py   # Usage examples
```

## 🚀 Quick Start

### 1. Train Model

```python
from apps.api.db.session import SessionLocal
from apps.ml.training import train_model_pipeline

db = SessionLocal()

# Train using ALL available historical data
results = train_model_pipeline(
    db=db,
    symbol="BTC/USDT",
    timeframe="1h",
    test_period_days=30,        # OOS test window size
    min_train_days=180          # Minimum training data required
)

print(f"Model ID: {results['model_id']}")
print(f"Version: {results['registry_version']}")
print(f"OOS AUC: {results['avg_metrics']['avg_roc_auc']:.4f}")
```

### 2. API Endpoints

#### Start Training
```bash
curl -X POST "http://localhost:8000/api/train/start" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "test_period_days": 30,
    "min_train_days": 180
  }'
```

#### Check Status
```bash
curl "http://localhost:8000/api/train/status/{job_id}"
```

#### List Models
```bash
curl "http://localhost:8000/api/train/models?symbol=BTC/USDT&timeframe=1h"
```

#### Deploy Model
```bash
curl -X POST "http://localhost:8000/api/train/models/deploy" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "version": "v1",
    "environment": "production"
  }'
```

#### Compare Versions
```bash
curl "http://localhost:8000/api/train/models/BTC_USDT/1h/compare?version1=v1&version2=v2"
```

## 🔬 Walk-Forward Validation Process

### Expanding Window Approach

```
Split 1: [====Train====][==Test==]
Split 2: [=======Train=======][==Test==]
Split 3: [============Train============][==Test==]
Split 4: [=================Train=================][==Test==]
...

Train window EXPANDS to include all historical data
Test window is fixed size (e.g., 30 days)
```

### Why Expanding Windows?

**Traditional Sliding Window:**
- Fixed-size training window
- Discards older data
- May miss long-term patterns

**Expanding Window (Our Approach):**
- Uses ALL historical data for training
- Captures long-term patterns and market regimes
- More robust to regime changes
- Better generalization

### Schema with Purge & Embargo

```
|<========== All Historical Data ==========>|<-P->|<-E->|<--- Test --->|
                                                  |           |
                                                Purge      Embargo
```

### Parameters

- **test_period_days**: OOS test window size (default: 30 days)
- **min_train_days**: Minimum training data required (default: 180 days)
- **purge_days**: Days to skip after train set (default: 2 days)
- **embargo_days**: Days to skip before test set (default: 1 day)

### Why Purge & Embargo?

**Purge**: Eliminates overlap between train and test caused by overlapping labels (e.g., triple barrier looks into future).

**Embargo**: Prevents lookahead bias - model doesn't see data immediately before test period.

## 📊 Triple Barrier Labeling

Model predicts whether price will hit:
- **TP (Take Profit)**: Profit target (e.g., +2%)
- **SL (Stop Loss)**: Stop loss (e.g., -1%)
- **Time**: Maximum holding period (e.g., 24 bars)

Label = 1 if TP hit first, 0 otherwise.

```python
from apps.ml.labeling import TripleBarrierLabeling

labeler = TripleBarrierLabeling(
    tp_pct=0.02,     # 2% take profit
    sl_pct=0.01,     # 1% stop loss
    time_bars=24     # 24h max holding period
)

labels_df = labeler.label_data(df, side='long')
```

## 🎯 Feature Engineering

### Available Features

1. **Technical Indicators**
   - EMAs (9, 21, 50, 200)
   - RSI (14)
   - Stochastic
   - MACD
   - ATR
   - Bollinger Bands
   - Ichimoku Cloud

2. **Support/Resistance**
   - Fibonacci retracements (0.382, 0.5, 0.618)
   - Pivot points (classic)

3. **Regime Detection**
   - Trend: uptrend/downtrend/sideways
   - Volatility: low/medium/high

4. **Microstructure** (placeholder for integration)
   - Spread
   - Depth imbalance
   - Realized volatility

```python
from apps.ml.features import FeatureEngineering

fe = FeatureEngineering()
df_features = fe.compute_all_features(df)

feature_cols = fe.get_feature_columns(df_features)
```

## 🏆 Model Registry

### Operations

#### Register Model
```python
from apps.ml.model_registry import ModelRegistry

registry = ModelRegistry()

version = registry.register_model(
    model_id="BTC_USDT_1h_20240101_120000",
    symbol="BTC/USDT",
    timeframe="1h",
    model_path=Path("./models/..."),
    metrics={'avg_roc_auc': 0.72, ...},
    metadata={...}
)
```

#### Deployment
```python
# Deploy to production
registry.deploy_model(
    symbol="BTC/USDT",
    timeframe="1h",
    version="v3",
    environment="production"
)

# Rollback
registry.rollback_deployment(
    symbol="BTC/USDT",
    timeframe="1h",
    environment="production"
)
```

#### Comparison
```python
comparison = registry.compare_models(
    symbol="BTC/USDT",
    timeframe="1h",
    version1="v1",
    version2="v2"
)

for metric, data in comparison['metrics_comparison'].items():
    print(f"{metric}: {data['pct_change']:+.2f}%")
```

## 📈 Performance Tracking

### Logging Predictions

```python
from apps.ml.performance_tracker import PerformanceTracker

tracker = PerformanceTracker()

# Log prediction batch
tracker.log_prediction_batch(
    model_id="BTC_USDT_1h_20240101_120000",
    symbol="BTC/USDT",
    timeframe="1h",
    predictions=predictions_df,  # timestamp, prediction, probability
    actuals=None,  # Fill in later
    metadata={'version': 'v1'}
)

# Update actuals later
tracker.update_actuals(
    model_id="BTC_USDT_1h_20240101_120000",
    batch_id="...",
    actuals=actuals_df  # timestamp, actual
)
```

### Degradation Detection

```python
degradation = tracker.detect_performance_degradation(
    model_id="BTC_USDT_1h_20240101_120000",
    metric='roc_auc',
    window_days=7,
    threshold_pct=10.0  # Alert if drop > 10%
)

if degradation['degraded']:
    print(f"⚠️ Performance dropped {degradation['degradation_pct']:.2f}%")
    # Trigger retrain or rollback
```

### Reports

```python
# Performance summary
summary = tracker.get_performance_summary(
    model_id="BTC_USDT_1h_20240101_120000",
    start_date=datetime(2024, 1, 1),
    end_date=datetime.utcnow()
)

# Generate report
report_path = tracker.generate_performance_report(
    model_id="BTC_USDT_1h_20240101_120000"
)
```

## 🔧 Configuration

### Environment Variables

```bash
# Model directories
MODEL_DIR=./models
REGISTRY_DIR=./model_registry
TRACKING_DIR=./performance_tracking

# Walk-forward parameters (expanding window)
WF_TEST_PERIOD_DAYS=30        # Fixed OOS test window
WF_MIN_TRAIN_DAYS=180         # Minimum training data required
WF_PURGE_DAYS=2               # Purge period
WF_EMBARGO_DAYS=1             # Embargo period

# Labeling
TP_PCT=0.02
SL_PCT=0.01
TIME_BARS=24
```

## 📋 Production Workflow

### 1. Data Preparation
```bash
# Backfill all available OHLCV data
python -m apps.ml.backfill --symbol BTC/USDT --timeframe 1h --all
```

### 2. Training
```python
# Train with expanding window walk-forward
# Uses ALL available historical data
results = train_model_pipeline(
    db=db,
    symbol="BTC/USDT",
    timeframe="1h",
    test_period_days=30,
    min_train_days=180
)
```

### 3. Evaluation
```python
# Check metrics across all splits
print(f"Avg OOS AUC: {results['avg_metrics']['avg_roc_auc']:.4f}")
print(f"Avg Precision: {results['avg_metrics']['avg_precision']:.4f}")
print(f"Number of splits: {results['num_splits']}")

# Feature importance
importance = results['feature_importance']
```

### 4. Deployment
```python
# Deploy best model
registry.deploy_model(
    symbol="BTC/USDT",
    timeframe="1h",
    version=results['registry_version'],
    environment="production"
)
```

### 5. Monitoring
```python
# Track predictions
tracker.log_prediction_batch(...)

# Check degradation daily
degradation = tracker.detect_performance_degradation(...)

if degradation['degraded']:
    # Alert team
    # Consider retrain or rollback
```

### 6. Retraining
```python
# Monthly retrain schedule
# Triggered by:
# - Performance degradation
# - New data availability
# - Market regime change

results = train_model_pipeline(...)
```

## 🧪 Testing

Run examples:
```bash
python examples/walkforward_example.py
```

Run unit tests:
```bash
pytest tests/test_walkforward.py
```

## 📊 Metrics

Pipeline tracks the following metrics for each split:

- **Accuracy**: Overall accuracy
- **Precision**: Precision of positive predictions
- **Recall**: Coverage of positive cases
- **F1 Score**: Harmonic mean of precision & recall
- **ROC AUC**: Area under ROC curve

Aggregated across splits:
- Mean and Std for each metric
- Best OOS AUC (for model selection)

## 🔍 Best Practices

1. **Data Leakage Prevention**
   - Always use purge & embargo
   - Don't use future information in features
   - Validate no temporal overlap

2. **Model Selection**
   - Select model with best OOS AUC
   - Don't optimize on test set
   - Use validation set for early stopping

3. **Deployment**
   - Test on staging before production
   - Monitor performance after deploy
   - Have rollback plan ready

4. **Retraining**
   - Regular schedule (e.g., monthly)
   - Trigger on degradation
   - Keep previous versions

## 🚨 Troubleshooting

### No OHLCV data
```
ValueError: No OHLCV data found
```
Solution: Run backfill process

### Insufficient splits
```
ValueError: No walk-forward splits generated
```
Solution: Check if you have enough data. Need at least `min_train_days + test_period_days`

### Training failures
```
Training failed for split X
```
Solution: Check class balance, feature NaNs, increase train size

### Performance degradation
```
degradation_pct > threshold
```
Solution: Retrain model or rollback deployment

## 📚 Additional Resources

- [Advances in Financial Machine Learning](https://www.amazon.com/Advances-Financial-Machine-Learning-Marcos/dp/1119482089) - Marcos López de Prado
- [Walk-Forward Optimization](https://en.wikipedia.org/wiki/Walk_forward_optimization)
- [Triple Barrier Method](https://quantdare.com/triple-barrier-method/)

## 🤝 Contributing

Improvement suggestions:
1. Hyperparameter optimization in walk-forward
2. Meta-labeling integration
3. More sophisticated ensemble methods (stacking)
4. Sample weighting by uniqueness
5. Fractional differentiation for stationarity

## 📝 Changelog

### v1.0.0 (2024-01-01)
- ✅ Walk-forward validation with expanding windows
- ✅ Model registry & versioning
- ✅ Performance tracking
- ✅ API endpoints
- ✅ Example scripts
- ✅ Documentation
