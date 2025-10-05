# TraderAI - Feature Documentation

## Overview

TraderAI is an AI-powered cryptocurrency futures trading signal system that uses machine learning models with walk-forward validation to generate high-probability trading signals for crypto futures markets.

---

## Core Features

### 1. **Data Management & Backfill**

#### Historical Data Backfill
- **Full History Import**: Fetch complete historical OHLCV (Open, High, Low, Close, Volume) data from Binance
- **Incremental Updates**: Automatically update latest candles every 15 minutes
- **Multi-Timeframe Support**: 1m, 5m, 15m, 1h, 4h, 1d timeframes
- **Progress Tracking**: Real-time backfill progress with ETA and speed metrics
- **Gap Detection**: Automatically identify and fill data gaps
- **Supported Pairs**:
  - BTC/USDT, ETH/USDT, BNB/USDT, XRP/USDT
  - ADA/USDT, SOL/USDT, DOGE/USDT, MATIC/USDT
  - DOT/USDT, AVAX/USDT, LINK/USDT, UNI/USDT

#### Database Status
- View total candles per trading pair
- Track first and last candle timestamps
- Monitor data freshness

---

### 2. **Machine Learning Pipeline**

#### Walk-Forward Validation
- **Expanding Window Training**: Train on ALL available historical data
- **Out-of-Sample Testing**: Rigorous validation on unseen future data
- **Purge & Embargo**: Prevent data leakage between train/test sets
- **Multiple Folds**: Generate multiple train/test splits for robust validation

#### Model Architecture
- **Ensemble Models**: Combine multiple algorithms for better predictions
  - LightGBM (Gradient Boosting)
  - XGBoost
  - Neural Networks (future)
- **Conformal Prediction**: Quantify prediction uncertainty
- **Feature Engineering**: 100+ technical indicators and market features

#### Training Features
- Automatic hyperparameter tuning
- Early stopping to prevent overfitting
- Feature importance analysis
- Model versioning and registry
- Deployment management (production/staging)

---

### 3. **Feature Engineering**

#### Technical Indicators
- **Moving Averages**: EMA (9, 21, 50, 200)
- **Momentum**: RSI (14), Stochastic (K/D), MACD
- **Volatility**: ATR (14), Bollinger Bands
- **Ichimoku Cloud**: Tenkan-sen, Kijun-sen, Senkou A/B, Chikou Span
- **Support/Resistance**: Fibonacci retracements, Pivot points

#### Market Microstructure
- Bid-ask spread analysis
- Order book depth imbalance
- Realized volatility
- Volume profile

#### Regime Detection
- Trend classification (uptrend, downtrend, sideways)
- Volatility regime (low, medium, high)
- Market condition awareness

---

### 4. **Labeling System (Triple Barrier Method)**

#### Advanced Labeling
- **Take Profit Barrier**: Define profit targets (default 2%)
- **Stop Loss Barrier**: Risk management (default 1%)
- **Time Barrier**: Maximum holding period (default 24 bars)
- **Binary Classification**: Predict if TP will be hit before SL

#### Label Quality
- Track which barrier was hit first
- Calculate actual returns achieved
- Measure bars to hit target
- Filter by label confidence

---

### 5. **Signal Generation**

#### Real-Time Signals
- Generate signals every 5 minutes (configurable)
- Multiple take-profit levels (TP1, TP2, TP3)
- Dynamic position sizing based on confidence
- Risk/reward ratio calculation

#### Signal Properties
- **Entry Price**: Optimal entry point
- **Take Profits**:
  - TP1: 30% position (conservative)
  - TP2: 40% position (moderate)
  - TP3: 30% position (aggressive)
- **Stop Loss**: Risk management level
- **Leverage**: Automatic leverage calculation
- **Expected Profit**: ML-predicted net profit %
- **Confidence Score**: Model certainty (0-1)

#### Signal Filters
- Spread check (reject if spread too wide)
- Liquidity check (ensure sufficient order book depth)
- Profit filter (minimum expected profit threshold)
- Correlation check (avoid correlated positions)

---

### 6. **Historical Signal Analysis**

#### Backtesting
- Generate signals on historical data
- Validate against actual market outcomes
- Track hit rate, win rate, and profitability
- Calculate realistic PnL including fees

#### Performance Metrics
- **Hit Rate TP1**: % of signals that hit first take profit
- **Win Rate**: Overall profitable signals %
- **Average Net Profit**: Mean profit per signal
- **Sharpe Ratio**: Risk-adjusted returns
- **Max Drawdown**: Worst losing streak

---

### 7. **Model Registry & Deployment**

#### Model Management
- Version control for all trained models
- Metadata tracking (training period, metrics, hyperparameters)
- Model comparison tools
- Performance degradation detection

#### Deployment Features
- **Environment Support**: Production, Staging, Development
- **Rollback Capability**: Instantly revert to previous version
- **A/B Testing**: Compare model versions
- **Canary Deployment**: Gradual rollout of new models

---

### 8. **Risk Management**

#### Position Sizing
- Kelly Criterion (optional)
- Fixed risk per trade (% of capital)
- Confidence-based sizing
- Maximum position limits

#### Risk Controls
- **Circuit Breakers**: Auto-pause on loss streaks
- **Kill Switch**: Emergency stop all trading
- **Max Drawdown Protection**: Reduce size after losses
- **Correlation Limits**: Avoid overexposure to correlated assets

---

### 9. **Performance Tracking**

#### Real-Time Monitoring
- Track model performance in production
- Compare predicted vs actual outcomes
- Monitor data drift and model degradation
- Alert on performance deterioration

#### Analytics
- Cumulative PnL tracking
- Win/loss distribution
- Trade duration analysis
- Market condition breakdown

---

### 10. **API & Integration**

#### REST API
- `/api/v1/train/start` - Start model training
- `/api/v1/train/status/{job_id}` - Get training progress
- `/api/v1/train/jobs` - List all training jobs
- `/api/v1/signals/` - Get active signals
- `/api/v1/backfill/start` - Start data backfill
- `/api/v1/models/` - Model registry endpoints

#### WebSocket
- Real-time signal updates
- Live training progress
- Market data streaming

---

### 11. **Admin Panel**

#### Data Management
- One-click full history backfill
- Monitor backfill progress (speed, ETA, completion %)
- View database status for all trading pairs

#### Training Dashboard
- Start training jobs with custom parameters
- Monitor training progress (fold number, accuracy, elapsed time)
- View training job history (last 24h)
- Error tracking and debugging

#### Historical Analysis
- Generate historical signals for full data range
- View signal performance with actual outcomes
- AI-generated signal explanations
- Filter by profitability, duration, status

#### System Metrics
- Hit Rate TP1 (system-wide)
- Average Net Profit
- Active models count
- Total signals and trades
- Win rate tracking

---

## Technical Architecture

### Backend Stack
- **FastAPI**: High-performance API framework
- **SQLAlchemy**: ORM for PostgreSQL
- **Celery**: Distributed task queue for async jobs
- **Redis**: Message broker and caching
- **PostgreSQL**: Primary database

### ML Stack
- **LightGBM**: Primary gradient boosting model
- **XGBoost**: Secondary ensemble component
- **Scikit-learn**: Model utilities and metrics
- **Pandas**: Data manipulation
- **TA-Lib**: Technical analysis library

### Frontend Stack
- **Next.js**: React framework
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first styling
- **Axios**: HTTP client

### Infrastructure
- **Docker**: Containerization
- **Docker Compose**: Multi-container orchestration
- **Alembic**: Database migrations
- **Celery Beat**: Periodic task scheduler

---

## Data Flow

1. **Data Ingestion**: Binance API → PostgreSQL
2. **Feature Engineering**: Raw OHLCV → 100+ features
3. **Labeling**: Triple barrier method → Binary labels
4. **Training**: Walk-forward validation → Ensemble model
5. **Registry**: Model storage → Version control
6. **Deployment**: Model selection → Production
7. **Inference**: Latest data → ML prediction → Signal
8. **Validation**: Actual outcome → Performance tracking

---

## Key Metrics & Targets

### Model Performance (Target)
- **Hit Rate TP1**: >55% (signals hitting first take profit)
- **Win Rate**: >50% (overall profitable trades)
- **Average Net Profit**: >0.5% per signal (after fees)
- **Sharpe Ratio**: >1.5 (risk-adjusted returns)
- **Max Drawdown**: <15% (worst losing period)

### Operational Metrics
- **Data Latency**: <1 minute (from exchange to database)
- **Signal Latency**: <30 seconds (from data to signal)
- **Model Inference**: <100ms per prediction
- **Backfill Speed**: >1000 candles/minute

---

## Future Roadmap

### Planned Features
- [ ] Multi-exchange support (Bybit, OKX)
- [ ] Transformer models (TFT - Temporal Fusion Transformer)
- [ ] Sentiment analysis integration (Twitter, Reddit)
- [ ] Automated strategy optimization
- [ ] Portfolio optimization (multi-asset allocation)
- [ ] Mobile app with push notifications
- [ ] Telegram/Discord bot integration
- [ ] Copy trading functionality
- [ ] Paper trading mode
- [ ] Advanced charting with signal overlays

### Research Areas
- Reinforcement learning for dynamic position sizing
- Graph neural networks for market correlation
- Attention mechanisms for feature importance
- Online learning for continuous model updates
- Meta-learning for rapid adaptation to new markets

---

## Getting Started

1. **Setup Environment**: `docker-compose up -d`
2. **Backfill Data**: Use admin panel to fetch BTC/USDT historical data
3. **Train Model**: Click "Train BTC/USDT Model" button
4. **Monitor Training**: Watch progress in real-time
5. **Generate Signals**: Automatic signal generation every 5 minutes
6. **View Performance**: Check system metrics and historical results

---

## Support & Documentation

- **API Docs**: http://localhost:8000/docs
- **Admin Panel**: http://localhost:3000/admin
- **Architecture**: See `ARCHITECTURE.md`
- **Project Structure**: See `PROJECT_STRUCTURE.md`
- **Quickstart Guide**: See `QUICKSTART.md`

---

## License

See `LICENSE` file for details.
