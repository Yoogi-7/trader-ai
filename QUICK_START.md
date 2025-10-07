# Quick Start - Zoptymalizowany System

## Status: ✅ GOTOWY DO BACKFILLU I TRENINGU

---

## 🚀 Szybkie Uruchomienie

### Krok 1: Backfill Danych (4 lata)

```bash
# Przez API
curl -X POST http://localhost:8000/api/v1/backfill/execute \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"],
    "timeframes": ["15m"],
    "lookback_days": 1460
  }'

# Sprawdź status
curl http://localhost:8000/api/v1/backfill/status
```

**Czas trwania:** ~2-4 godziny (zależnie od API rate limits)

---

### Krok 2: Trening Modelu

```bash
# Trenuj BTC/USDT z nowymi parametrami
curl -X POST http://localhost:8000/api/v1/train \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "timeframe": "15m",
    "test_period_days": 30,
    "min_train_days": 365,
    "use_expanding_window": true
  }'

# Monitor progress
docker logs -f traderai-worker-training3
```

**Czas trwania:** ~30-60 minut na symbol

**Spodziewane metryki:**
- Accuracy: >60% (target 70%)
- ROC-AUC: >60%
- Recall: 30-50% (bardziej selektywny)

---

### Krok 3: Generuj Sygnały Historyczne

```bash
# Backtest
curl -X POST http://localhost:8000/api/v1/signals/generate-historical \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "timeframe": "15m",
    "lookback_days": 365
  }'

# Sprawdź wyniki
curl http://localhost:8000/api/v1/signals/historical/jobs
```

---

### Krok 4: Weryfikacja Accuracy

```bash
docker exec traderai-api python -c "
from sqlalchemy import create_engine, text
from apps.api.config import settings

engine = create_engine(str(settings.DATABASE_URL).replace('+asyncpg', ''))

with engine.connect() as conn:
    result = conn.execute(text('''
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN actual_net_pnl_usd > 0 THEN 1 END) as winners,
            AVG(actual_net_pnl_pct) as avg_pnl,
            AVG(confidence) as avg_conf
        FROM historical_signal_snapshots
        WHERE actual_net_pnl_pct IS NOT NULL
    '''))
    
    row = result.fetchone()
    win_rate = (row[1] / row[0] * 100) if row[0] > 0 else 0
    
    print(f'Total Signals: {row[0]}')
    print(f'Winners: {row[1]}')
    print(f'Win Rate: {win_rate:.2f}%')
    print(f'Avg PnL: {row[2]:.2f}%')
    print(f'Avg Confidence: {row[3]:.2f}')
"
```

**Target:**
- Win Rate: >50%
- Avg PnL: >2%
- Avg Confidence: >0.65

---

## 📊 Co Zostało Zmienione?

### 1. Nowe Wskaźniki (20+)
✅ VWAP, StochRSI, Keltner, ADX, Supertrend  
✅ OBV, Volume Profile, OBI  
✅ Swing Points, Dynamic Fibonacci  
✅ EMA Slopes, Consolidation Zones, RSI Divergence  
❌ Ichimoku (look-ahead bias removed)

### 2. Adaptive TP/SL
Dostosowują się do:
- Confidence (0.65-0.70+)
- Volatility regime (low/normal/high)

### 3. Wyższe Standardy
- MIN_CONFIDENCE: 0.65 (was 0.55)
- MIN_PROFIT: 2.0% (was 0.8%)
- MIN_ACCURACY: 70% (was 65%)

### 4. Więcej Danych Treningowych
- Quick mode: 180 dni (was 90)
- Full mode: 365 dni (was 180)

---

## 🔍 Monitoring

### Check System Status

```bash
curl http://localhost:8000/api/v1/system/status
```

### Check Active Signals

```bash
curl http://localhost:8000/api/v1/signals
```

### Check Training Jobs

```bash
curl http://localhost:8000/api/v1/train/jobs
```

### Logs

```bash
# API
docker logs -f traderai-api

# Workers
docker logs -f traderai-worker
docker logs -f traderai-worker-training3

# Beat
docker logs -f traderai-beat
```

---

## ⚠️ Troubleshooting

### Problem: Feature calculation errors

```bash
# Check if all new indicators are calculating correctly
docker exec traderai-api python -c "
from apps.ml.features import FeatureEngineering
import pandas as pd
import numpy as np

# Test with dummy data
df = pd.DataFrame({
    'timestamp': pd.date_range('2024-01-01', periods=500, freq='15min'),
    'open': np.random.rand(500) * 100 + 60000,
    'high': np.random.rand(500) * 100 + 60100,
    'low': np.random.rand(500) * 100 + 59900,
    'close': np.random.rand(500) * 100 + 60000,
    'volume': np.random.rand(500) * 1000000
})

fe = FeatureEngineering()
enriched = fe.compute_all_features(df)

print(f'Original columns: {len(df.columns)}')
print(f'Enriched columns: {len(enriched.columns)}')
print(f'New features: {len(enriched.columns) - len(df.columns)}')
print()
print('Sample new features:')
for col in ['vwap', 'stochrsi', 'keltner_upper', 'obv', 'supertrend_direction']:
    if col in enriched.columns:
        print(f'  ✅ {col}')
    else:
        print(f'  ❌ {col} MISSING!')
"
```

### Problem: Model training fails

Check logs for specific errors. Common issues:
- Not enough data (need 365+ days)
- NaN values in features
- Memory issues (reduce batch size)

### Problem: No signals generated

```bash
# Check model deployment
docker exec traderai-api python -c "
from apps.ml.model_registry import ModelRegistry

registry = ModelRegistry()
deployments = registry.index.get('deployments', {})

print('Deployed models:')
for key, dep in deployments.items():
    print(f'  {key}: {dep.get(\"model_id\")} (version {dep.get(\"version\")})')
"
```

---

## 📚 Dokumentacja

- **OPTIMIZATION_CHANGES.md** - Szczegółowy opis wszystkich zmian
- **CHANGES_SUMMARY.md** - Podsumowanie poprzednich iteracji
- **README.md** - Ogólna dokumentacja projektu

---

## 🎯 Success Criteria

### Przed Uruchomieniem Produkcji:
- [ ] Backtest accuracy > 70%
- [ ] Average net profit > 2%
- [ ] Win rate > 50%
- [ ] Max drawdown < 15%
- [ ] At least 100 historical signals tested

### Jeśli NIE spełnia kryteriów:
1. Zwiększ MIN_CONFIDENCE do 0.70
2. Dodaj więcej feature selection (SHAP)
3. Rozważ ensemble z CatBoost
4. Dodaj regression component do predykcji magnitude

---

**Powodzenia!** 🚀
