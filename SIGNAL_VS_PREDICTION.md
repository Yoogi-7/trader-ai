# 🔍 Performance Tracking vs Trading Signals - Różnica

## Data: 2025-10-06 18:25

---

## ❌ To NIE jest sygnał tradingowy!

### Co zobaczyłeś:
```json
{
  "batch_id": "BTC_USDT_15m_20251005_161731_20251006_182449",
  "model_id": "BTC_USDT_15m_20251005_161731",
  "symbol": "BTC/USDT",
  "probability": 0.46424101902600157,
  "confidence": 0.5357589809739984,
  "side": "short"
}
```

**To jest**: 📊 **Performance Tracking Log** (zapis predykcji do monitorowania)

**To NIE jest**: 🚫 **Trading Signal** (gotowy do wykonania trade)

---

## 📊 Performance Tracking Log

### Cel:
- Monitorowanie **każdej predykcji** modelu
- Tracking długoterminowej accuracy
- Drift detection (czy model się psuje)
- Research i analiza

### Gdzie:
- `/performance_tracking/BTC_USDT_15m_*/batches/*.json`
- Zapisuje się **co 5 minut** automatycznie

### Co zawiera:
- Probability (surowa predykcja modelu: 0-1)
- Confidence (pewność: 0.5-1.0)
- Side (long/short)
- Features użyte do predykcji
- **BRAK** TP/SL, position size, etc.

### Przykład:
```
Godzina 18:15:
- Model widzi BTC @ $62,800
- Probability: 0.464 (46.4%)
- Side: SHORT (bo < 0.5)
- Confidence: 0.536 (53.6%)
```

**To tylko surowa predykcja - NIE sygnał do trade!**

---

## 🎯 Trading Signal (Prawdziwy Sygnał)

### Cel:
- **Gotowy do wykonania** trade
- Zawiera **wszystkie parametry** (TP, SL, size, leverage)
- Przeszedł **wszystkie filtry** (min 2% profit, liquidity, etc.)

### Gdzie:
- Tabela `signals` w bazie danych
- API endpoint: `/api/v1/signals`
- WebSocket broadcast do UI

### Co zawiera:
```json
{
  "signal_id": "signal_BTC_USDT_abc123",
  "symbol": "BTC/USDT",
  "side": "LONG",
  "entry_price": 62800.0,
  "tp1_price": 63200.0,
  "tp2_price": 63800.0,
  "tp3_price": 64600.0,
  "sl_price": 62400.0,
  "leverage": 20,
  "position_size_usd": 1000.0,
  "quantity": 0.0159,
  "expected_net_profit_pct": 3.5,  // ✅ > 2%
  "confidence": 0.65,
  "risk_reward_ratio": 2.8,
  "status": "ACTIVE"
}
```

**To jest kompletny setup gotowy do trade!**

---

## 🚫 Dlaczego nie ma sygnałów?

### Sprawdźmy logi:

```bash
[2025-10-05 19:43:28] Signal rejected for BTC/USDT:
Expected net profit 0.39% < minimum 2.0%

[2025-10-05 20:26:55] Signal rejected for BTC/USDT:
Expected net profit 0.35% < minimum 2.0%
```

### Problem:
1. **Model generuje predykcje** ✅
2. **System próbuje stworzyć sygnał** ✅
3. **Kalkuluje expected profit**: 0.35-0.39% ❌
4. **Filtr 2%**: Expected profit < 2% → **ODRZUĆ** ❌

### Dlaczego tak niski profit?

**Powód**: Obecnie używasz **STARYCH TP/SL multiplierów**:
```python
atr_multiplier_sl = 1.2   # Szeroki SL
atr_multiplier_tp1 = 1.5  # Niski TP (~2% gross)
atr_multiplier_tp2 = 2.5  # Niski TP (~3% gross)
```

**Kalkulacja**:
- Gross profit (TP avg): ~2.5%
- Koszty (fees + slippage + funding): ~0.32%
- **Net profit**: 2.5% - 0.32% = **~2.2%**

Ale przy niskiej zmienności (mały ATR):
- Gross profit: ~1.5%
- Koszty: ~0.32%
- **Net profit**: 1.5% - 0.32% = **~1.2%** ❌ < 2%

---

## ✅ Rozwiązanie: Użyj Nowych Multiplierów

### Zastosowałeś już zmiany w kodzie:

```python
# NOWE (apps/ml/signal_engine.py)
atr_multiplier_sl = 1.0   # Ciasniejszy SL
atr_multiplier_tp1 = 2.0  # Wyższy TP (~3-4% gross)
atr_multiplier_tp2 = 3.5  # Wyższy TP (~5-7% gross)
atr_multiplier_tp3 = 6.0  # Wyższy TP (~9-12% gross)
```

**Efekt**:
- Gross profit (TP avg): ~5%
- Koszty: ~0.32%
- **Net profit**: 5% - 0.32% = **~4.7%** ✅ > 2%

### Restart wymagany:
```bash
docker-compose restart worker api
```

**Po restarcie**: System zacznie generować sygnały które spełniają filtr 2%!

---

## 📊 Co się dzieje teraz (co 5 minut):

### 1. **Celery Beat** wywołuje task:
```python
'generate-signals-every-5-minutes': {
    'task': 'signals.generate',
    'schedule': 300.0,
}
```

### 2. **Worker** wykonuje:
1. Pobiera najnowsze dane OHLCV
2. Oblicza features (RSI, MACD, etc.)
3. **Model przewiduje**: probability = 0.464
4. **Performance Tracker** zapisuje do pliku ✅
5. **Signal Generator** próbuje stworzyć sygnał:
   - Entry: $62,800
   - TP1: $63,200 (1.5x ATR) → gross ~0.6%
   - TP2: $63,600 (2.5x ATR) → gross ~1.3%
   - TP3: $64,200 (4.0x ATR) → gross ~2.2%
   - **Avg gross profit**: ~1.4%
   - **Koszty**: -0.32%
   - **Net profit**: **1.1%** ❌ < 2%
6. **Filtr 2%**: ODRZUĆ ❌
7. Log: "Signal rejected for BTC/USDT: Expected net profit 1.1% < minimum 2.0%"

### 3. **Sygnał NIE jest zapisywany do bazy**
- Tabela `signals` pozostaje pusta
- Brak WebSocket broadcast
- Brak w UI

---

## 🔄 Po Restarcie (z nowymi multiplierami):

### 1. **Worker** wykonuje:
1. Pobiera najnowsze dane OHLCV
2. Oblicza features
3. Model przewiduje: probability = 0.65
4. Performance Tracker zapisuje ✅
5. Signal Generator tworzy sygnał:
   - Entry: $62,800
   - TP1: $63,600 (**2.0x ATR**) → gross ~1.3%
   - TP2: $64,800 (**3.5x ATR**) → gross ~3.2%
   - TP3: $66,400 (**6.0x ATR**) → gross ~5.7%
   - **Avg gross profit**: ~3.5%
   - **Koszty**: -0.32%
   - **Net profit**: **3.2%** ✅ > 2%
6. **Filtr 2%**: AKCEPTUJ ✅
7. **Zapisuje do bazy** `signals` ✅
8. **WebSocket broadcast** → UI ✅
9. **Możesz wykonać trade!** 🎯

---

## 📍 Sprawdź Prawdziwe Sygnały

### W bazie danych:
```bash
docker-compose exec db psql -U traderai -d traderai -c \
  "SELECT signal_id, symbol, side, entry_price,
          expected_net_profit_pct, confidence, status, created_at
   FROM signals
   ORDER BY created_at DESC LIMIT 10;"
```

### Przez API:
```bash
curl http://localhost:8000/api/v1/signals
```

### W UI:
```
http://localhost:3000/signals
```

---

## 🎯 Podsumowanie

| Typ | Gdzie | Częstotliwość | Filtr 2%? | Do trade? |
|-----|-------|---------------|-----------|-----------|
| **Performance Log** | `/performance_tracking/` | Co 5 min | ❌ NIE | ❌ NIE |
| **Trading Signal** | Baza `signals` | Gdy profit > 2% | ✅ TAK | ✅ TAK |

### Twój plik JSON:
- ❌ **NIE** jest sygnałem tradingowym
- ✅ **JEST** logiem predykcji do monitorowania
- ❌ **NIE** przeszedł filtru 2% (expected profit za niski)
- ❌ **NIE** został zapisany do `signals`

### Prawdziwy sygnał:
- ✅ W bazie danych `signals`
- ✅ Ma wszystkie parametry (TP, SL, size)
- ✅ Przeszedł filtr 2% profit
- ✅ Status = ACTIVE
- ✅ Gotowy do trade

---

## 🚀 Następne Kroki

1. **Restart systemu** z nowymi multiplierami:
   ```bash
   docker-compose restart worker api
   ```

2. **Poczekaj 5-10 minut** (następny cycle)

3. **Sprawdź sygnały**:
   ```bash
   docker-compose exec db psql -U traderai -d traderai -c \
     "SELECT COUNT(*) FROM signals WHERE created_at > NOW() - INTERVAL '1 hour';"
   ```

4. **Jeśli nadal brak**:
   - Sprawdź logi: `docker-compose logs worker --tail=50 | grep "Signal rejected"`
   - Możliwe że rynek jest w low volatility (mały ATR)
   - Poczekaj na większą zmienność lub dodaj więcej symboli

---

**Status**: ✅ System działa, ale sygnały odrzucane przez filtr 2% (za małe TP). Po restarcie z nowymi multiplierami powinno działać!

---

**Ostatnia aktualizacja**: 2025-10-06 18:30
