# TraderAI - System Architecture

## High-Level Design

TraderAI is designed as a modular, production-ready trading signal system with clear separation of concerns:

```
┌──────────────────────────────────────────────────────────────────┐
│                        Presentation Layer                         │
│  ┌────────────────────┐          ┌───────────────────────────┐  │
│  │  User Dashboard    │          │    Admin Panel            │  │
│  │  (Next.js)         │          │    (Next.js)              │  │
│  └────────────────────┘          └───────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              ↕ HTTP/WebSocket
┌──────────────────────────────────────────────────────────────────┐
│                         API Layer (FastAPI)                       │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────────┐   │
│  │ Signals  │ Backtest │ Backfill │ Training │   Settings   │   │
│  └──────────┴──────────┴──────────┴──────────┴──────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                              ↕
┌──────────────────────────────────────────────────────────────────┐
│                      Business Logic Layer                         │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Signal Generation Engine                                  │  │
│  │  - Entry/Exit Calculation  - Position Sizing               │  │
│  │  - ≥2% Profit Filter      - Risk Management                │  │
│  └────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  ML Training Pipeline                                      │  │
│  │  - Feature Engineering    - Walk-Forward Validation        │  │
│  │  - Ensemble Models        - Drift Detection                │  │
│  └────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Backtest Engine                                           │  │
│  │  - Cost Modeling          - Partial TP/Trailing SL         │  │
│  │  - Performance Metrics    - Hit Rate Calculation           │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              ↕
┌──────────────────────────────────────────────────────────────────┐
│                      Data Access Layer                            │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐   │
│  │ CCXT Client    │  │ DB Models      │  │  Cache (Redis)   │   │
│  │ (Exchange API) │  │ (SQLAlchemy)   │  │                  │   │
│  └────────────────┘  └────────────────┘  └──────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                              ↕
┌──────────────────────────────────────────────────────────────────┐
│                     Persistence Layer                             │
│  ┌────────────────────────────┐  ┌──────────────────────────┐   │
│  │ PostgreSQL + TimescaleDB   │  │      Redis               │   │
│  │ - OHLCV (hypertable)       │  │  - Cache                 │   │
│  │ - Features                 │  │  - Celery broker         │   │
│  │ - Signals, Models, Metrics │  │                          │   │
│  └────────────────────────────┘  └──────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Data Pipeline

**CCXT Client** ([apps/ml/ccxt_client.py](apps/ml/ccxt_client.py))
- Fetches OHLCV data from exchanges (Bitget USDT-margined swaps)
- Handles rate limiting, retries, error handling
- Supports multiple timeframes (1m → 1d)

**Backfill Service** ([apps/ml/backfill.py](apps/ml/backfill.py))
- Resumable downloads with checkpointing
- Stores `last_completed_ts` in DB
- Progress tracking (%, ETA, speed)
- Gap detection and auto-fill

**TimescaleDB Integration**
- Hypertable for OHLCV (partitioned by time)
- Automatic compression (30+ days old)
- Fast time-range queries

### 2. Feature Engineering

**FeatureEngineering** ([apps/ml/features.py](apps/ml/features.py))

Computes 40+ features across categories:

1. **Trend Indicators**
   - EMAs (9, 21, 50, 200)
   - MACD (12, 26, 9)
   - Ichimoku Cloud

2. **Momentum**
   - RSI (14)
   - Stochastic (14, 3, 3)

3. **Volatility**
   - ATR (14)
   - Bollinger Bands (20, 2σ)

4. **Support/Resistance**
   - Fibonacci retracements (0.382, 0.5, 0.618)
   - Pivot points (classic)

5. **Market Microstructure**
   - Spread (bps)
   - Depth imbalance
   - Realized volatility

6. **Regime Detection**
   - Trend: uptrend/downtrend/sideways (EMA crossovers)
   - Volatility: low/medium/high (ATR percentile)

7. **Sentiment** (plugin interface)
   - Placeholder for external sentiment data

### 3. Labeling Strategy

**Triple Barrier Method** ([apps/ml/labeling.py](apps/ml/labeling.py))

For each candle, looks forward to find which barrier is hit first:
- **TP Barrier**: +2% (configurable)
- **SL Barrier**: -1% (configurable)
- **Time Barrier**: 24 candles (configurable)

Returns:
- `hit_barrier`: "tp" / "sl" / "time"
- `bars_to_hit`: Number of candles
- `return_pct`: Actual return

This creates balanced labels that account for both profitability AND holding time.

### 4. ML Models

**Ensemble Architecture** ([apps/ml/models.py](apps/ml/models.py))

```
┌─────────────────────────────────────────┐
│         Input Features (40+)            │
└─────────────────┬───────────────────────┘
                  │
      ┌───────────┴───────────┐
      │                       │
┌─────▼─────┐         ┌───────▼────────┐
│  LightGBM │         │    XGBoost     │
│  (GBDT)   │         │   (GBDT)       │
└─────┬─────┘         └───────┬────────┘
      │                       │
      └───────────┬───────────┘
                  │ Average
            ┌─────▼──────┐
            │  Ensemble  │
            │ Prediction │
            └─────┬──────┘
                  │
         ┌────────▼─────────┐
         │ Conformal        │
         │ Calibration      │
         │ (MAPIE)          │
         └────────┬─────────┘
                  │
            ┌─────▼──────┐
            │ Confidence │
            │  + Filter  │
            │   (≥55%)   │
            └────────────┘
```

**Conformal Prediction**
- Calibrates probabilities using held-out calibration set
- Ensures confidence ≥ threshold → actual accuracy ≥ threshold
- Filters low-confidence predictions

### 5. Walk-Forward Validation

**WalkForwardValidator** ([apps/ml/walkforward.py](apps/ml/walkforward.py))

Prevents data leakage through:

```
Train Period (180d) | Purge (2d) | Embargo (1d) | Test Period (30d)
────────────────────┼────────────┼──────────────┼──────────────────>
                    │            │              │
                    └────────────┘──────────────┘
                    Data excluded from both sets

- Purge: Removes overlap from label lookahead
- Embargo: Prevents using future data to predict past
```

Slides window forward:
1. Train on 180 days
2. Skip 2 days (purge)
3. Skip 1 day (embargo)
4. Test on 30 days
5. Advance start by 30 days, repeat

### 6. Signal Generation

**SignalGenerator** ([apps/ml/signal_engine.py](apps/ml/signal_engine.py))

**Step 1: TP/SL Calculation** (ATR-based)
```python
SL = entry ± (1.5 × ATR)
TP1 = entry ± (1.0 × ATR)  # 30% exit
TP2 = entry ± (2.0 × ATR)  # 40% exit
TP3 = entry ± (3.0 × ATR)  # 30% exit
```

**Step 2: Position Sizing**
```python
risk_usd = capital × risk_per_trade  # 1%/2%/3% based on profile
sl_distance_pct = |entry - SL| / entry
position_size = risk_usd / sl_distance_pct
leverage = min(position_size / capital, max_lev)
```

**Step 3: Expected Profit Calculation**
```python
# Gross profit (weighted avg of TPs)
avg_exit = (TP1×30% + TP2×40% + TP3×30%)
gross_profit_pct = (avg_exit - entry) / entry

# Costs
entry_cost = position_size × (maker_fee + slippage/2)
exit_cost = position_size × (taker_fee + slippage) × 3  # 3 exits
funding_cost = position_size × funding_rate × hold_hours

# Net profit
net_profit = gross_profit - entry_cost - exit_cost - funding_cost
net_profit_pct = (net_profit / position_size) × 100
```

**Step 4: Filter** ⚠️ CRITICAL
```python
if net_profit_pct < 2.0:
    return None  # REJECT SIGNAL
```

### 7. Backtesting

**Backtester** ([apps/ml/backtest.py](apps/ml/backtest.py))

Simulates realistic execution:

1. **Entry**: Apply slippage, deduct margin
2. **Position Management**:
   - Check each candle for TP/SL hits
   - Partial exits at TP1/TP2/TP3
   - Trailing SL after TP1
   - Time stop (48h max)
3. **Exit**: Calculate fees, slippage, funding
4. **PnL**: Update capital, equity curve, drawdown

**Metrics**:
- `hit_rate_tp1`: % trades hitting TP1 ✅ Target: ≥55%
- `win_rate`: % profitable trades
- `profit_factor`: Total wins / Total losses
- `max_drawdown_pct`: Peak-to-trough decline
- `sharpe_ratio`: Risk-adjusted returns

### 8. Drift Detection

**DriftDetector** ([apps/ml/drift.py](apps/ml/drift.py))

Monitors two types of drift:

**1. Feature Drift**
- PSI (Population Stability Index) for each feature
- KS (Kolmogorov-Smirnov) test
- Threshold: PSI > 0.15 or KS > 0.1

**2. Prediction Drift**
- Compares current vs. baseline prediction distribution
- Same PSI/KS tests

**Auto-Retrain Trigger**:
- Run daily check
- If drift detected → queue retrain job
- Train new model on recent data
- Compare OOS metrics vs. current model
- Deploy if better, else rollback

### 9. Async Task Queue

**Celery Workers** ([apps/ml/worker.py](apps/ml/worker.py))

**Tasks**:
1. `backfill.execute`: Run backfill jobs
2. `training.train_model`: Train ML models
3. `signals.generate`: Generate signals (every 5 min)
4. `drift.monitor`: Check drift (daily)

**Beat Schedule**:
```python
{
    'generate-signals': {'schedule': 300.0},  # 5 min
    'monitor-drift': {'schedule': 86400.0},   # 1 day
}
```

## Database Schema

### Key Tables

**ohlcv** (TimescaleDB hypertable)
- symbol, timeframe, timestamp (composite unique)
- open, high, low, close, volume
- Partitioned by time (7-day chunks)
- Compressed after 30 days

**feature_sets**
- All computed features for each (symbol, tf, ts)
- 40+ columns

**labels**
- Triple-barrier labels for training

**signals**
- Generated trading signals
- Entry, TP1/2/3, SL, leverage, sizing
- `passed_profit_filter` flag ✅
- `expected_net_profit_pct` ✅

**model_registry**
- Model metadata, hyperparameters
- OOS metrics (hit_rate_tp1, avg_net_profit_pct) ✅
- Artifact paths

**backfill_jobs**
- Job status, progress, checkpoints ✅
- `last_completed_ts` for resume ✅

## API Endpoints

### Signals
- `GET /api/v1/signals/live` - Active signals (filtered by risk profile)
- `GET /api/v1/signals/history` - Historical signals
- `GET /api/v1/signals/{signal_id}` - Signal details

### Backtest
- `POST /api/v1/backtest/run` - Run backtest simulation

### Backfill
- `POST /api/v1/backfill/start` - Start backfill job ✅
- `GET /api/v1/backfill/status/{job_id}` - Job status ✅

### Training
- `POST /api/v1/train/start` - Trigger model training

### Settings
- `GET /api/v1/settings` - Get system configuration

## Performance Optimizations

1. **TimescaleDB**:
   - Hypertable partitioning → Fast time-range queries
   - Compression → 90% storage savings
   - Continuous aggregates (future enhancement)

2. **Redis Caching**:
   - Active signals (5 min TTL)
   - Model predictions (15 min TTL)
   - System metrics (1 min TTL)

3. **Async Processing**:
   - Celery for long-running tasks
   - Non-blocking API responses

4. **Database Indexes**:
   - (symbol, timeframe, timestamp) composite
   - symbol, timestamp separately
   - status, risk_profile for filtering

## Security Considerations

1. **API Keys**: Store in env vars, never commit
2. **Database**: Password-protected, no public exposure
3. **API**: Rate limiting, CORS restrictions
4. **Secrets**: Use SECRET_KEY for JWT tokens
5. **Sandbox Mode**: Test with fake money first

## Scalability

**Current Capacity**:
- 10-20 symbols × 4 timeframes = 40-80 models
- Signal generation: 300 signals/day
- Backfill speed: ~10k candles/min

**Scaling Options**:
1. Horizontal: Add more Celery workers
2. Database: PostgreSQL read replicas
3. Caching: Redis cluster
4. ML: Distribute training across GPUs
5. API: Load balancer + multiple instances

## Testing Strategy

1. **Unit Tests**: Individual components (features, labeling, models)
2. **Integration Tests**: End-to-end signal generation
3. **Critical Tests**: ✅
   - Profit filter (≥2%)
   - Backfill resume
   - Walk-forward validation
   - Hit rate calculation

## Monitoring & Observability

**Metrics to Track**:
- Hit rate (TP1, TP2, TP3) ✅
- Average net profit ✅
- Win rate, profit factor
- Model drift scores
- Backfill progress
- API latency
- Error rates

**Future Enhancements**:
- Prometheus + Grafana dashboards
- Alerting (Telegram, Discord)
- Trading journal (track live performance)
- A/B testing (compare model versions)
