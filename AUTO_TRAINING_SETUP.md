# 🤖 Auto-Training System - Setup Guide

System został pomyślnie skonfigurowany! Oto jak go używać:

## 📋 Co zostało zaimplementowane

### 1. **Quick Training Mode**
- Szybki trening (14 dni test, 90 dni train) dla natychmiastowej generacji sygnałów
- Automatyczne przejście do pełnego treningu po pierwszym cyklu

### 2. **Continuous Auto-Training**
- Automatyczny trening raz w tygodniu
- Ewolucja parametrów dla lepszej skuteczności
- Cel: min 1% zwrot, min 60% accuracy, maksymalna liczba sygnałów

### 3. **Auto-Leverage System**
- Automatyczny dobór dźwigni (1-20x) na podstawie:
  - Pewności modelu (confidence)
  - Zmienności rynku (ATR)
  - Profilu ryzyka

### 4. **Parameter Evolution**
- Inteligentna optymalizacja parametrów TP/SL
- Historia ewolucji zapisywana w bazie
- Adaptacja do zmieniających się warunków rynku

## 🚀 Jak uruchomić

### Krok 1: Uruchom migrację bazy danych

```bash
docker-compose exec api alembic upgrade head
```

### Krok 2: Uruchom auto-training przez API

```bash
# Start auto-training (quick mode)
curl -X POST http://localhost:8000/api/v1/auto-train/start \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["BTC/USDT", "ETH/USDT", "BNB/USDT"],
    "timeframe": "15m",
    "quick_start": true
  }'
```

To natychmiast uruchomi:
1. **Quick training** dla BTC, ETH, BNB (займе ~2-3 godziny zamiast 3 dni)
2. Po zakończeniu quick training → system zacznie generować sygnały
3. Raz w tygodniu (co 7 dni) → automatyczny pełny retraining z ewolucją parametrów

### Krok 3: Sprawdź status

```bash
# Status auto-training
curl http://localhost:8000/api/v1/auto-train/status

# Szczegóły konfiguracji (włącznie z generacjami i score)
curl http://localhost:8000/api/v1/auto-train/config
```

## 🎯 Endpointy API

### Start Auto-Training
```bash
POST /api/v1/auto-train/start
{
  "symbols": ["BTC/USDT", "ETH/USDT"],
  "timeframe": "15m",
  "quick_start": true
}
```

### Stop Auto-Training
```bash
POST /api/v1/auto-train/stop
```

### Get Status
```bash
GET /api/v1/auto-train/status
```

### Get Config (z evolution stats)
```bash
GET /api/v1/auto-train/config
```

### Manual Trigger
```bash
POST /api/v1/auto-train/trigger
```

### Update Config
```bash
PUT /api/v1/auto-train/config
{
  "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
  "quick_start": false
}
```

## ⚙️ Parametry w `.env` / config.py

Nowe parametry zostały dodane:

```python
# Minimalne wymagania
MIN_NET_PROFIT_PCT = 1.0  # Zmniejszone z 2.0% → więcej sygnałów
MIN_ACCURACY_TARGET = 0.60  # Target 60% accuracy
MIN_CONFIDENCE_THRESHOLD = 0.50  # Zmniejszone dla więcej sygnałów

# Auto-Training
AUTO_TRAINING_ENABLED = False  # Kontrolowane przez API
AUTO_TRAINING_INTERVAL_HOURS = 12
QUICK_TRAINING_TEST_DAYS = 14
QUICK_TRAINING_MIN_DAYS = 90
FULL_TRAINING_TEST_DAYS = 30
FULL_TRAINING_MIN_DAYS = 180

# Auto-Leverage
AUTO_LEVERAGE = True  # Automatyczny dobór dźwigni
```

## 🔍 Jak to działa

### 1. Quick Start Flow
```
1. POST /auto-train/start (quick_start=true)
2. System uruchamia quick training:
   - Test period: 14 dni
   - Min train: 90 dni
   - Trening zajmie ~2-3h zamiast 3 dni
3. Model jest gotowy do generowania sygnałów
4. Po pierwszym cyklu: quick_mode → false
5. Następne treningi będą pełne (30/180 dni)
```

### 2. Continuous Training Cycle
```
Raz w tygodniu (co 7 dni) (Celery beat):
1. Sprawdź czy modele wymagają retreningu
2. Dla każdego symbolu:
   - Uruchom trening z aktualnymi parametrami
   - Oceń wyniki (accuracy, recall, AUC)
   - Wyewoluuj parametry dla następnej generacji
3. Zapisz najlepszy model
4. Auto-deploy do produkcji
```

### 3. Parameter Evolution
```python
# Generacja 1: Początkowe parametry
tp_mult = 2.0, sl_mult = 1.0

# Jeśli accuracy < 60%:
tp_mult → 2.1 (wyższe TP)
sl_mult → 0.95 (ciaśniejszy SL)

# Jeśli recall < 30% (mało sygnałów):
tp_mult → 1.9 (niższe TP)
sl_mult → 1.05 (luźniejszy SL)

# Jeśli AUC > 60% i recall > 30%:
tp_mult → 2.2 (jeszcze wyższe TP dla lepszych zwrotów)
```

### 4. Auto-Leverage Calculation
```python
# Bazowa dźwignia na podstawie confidence
if confidence < 0.55: leverage = 3x
elif confidence < 0.60: leverage = 5x
elif confidence < 0.70: leverage = 8x
else: leverage = 12x

# Korekta na podstawie zmienności (ATR%)
if atr_pct > 3.0: leverage *= 0.6
elif atr_pct > 2.0: leverage *= 0.8

# Przykład:
# BTC, confidence=0.72, atr=2.5% → 12x * 0.8 = 9x
```

## 📊 Monitoring

### Celery Worker Logs
```bash
docker-compose logs -f worker | grep -E "Auto-training|Training cycle|Evolution"
```

### Database Status
```bash
docker-compose exec db psql -U traderai -d traderai -c \
  "SELECT * FROM auto_training_config;"
```

### Training Progress
```bash
docker-compose exec db psql -U traderai -d traderai -c \
  "SELECT symbol, status, progress_pct, avg_roc_auc
   FROM training_jobs
   ORDER BY created_at DESC
   LIMIT 5;"
```

## 🎛️ Control Flow

### Standardowy przepływ pracy:

1. **Inicjalizacja (raz)**
   ```bash
   # Uruchom migracje
   docker-compose exec api alembic upgrade head

   # Włącz auto-training
   curl -X POST .../auto-train/start -d '{"quick_start": true}'
   ```

2. **System pracuje automatycznie**
   - Co 12h: auto-retraining
   - Co 5min: generowanie sygnałów z najnowszym modelem
   - Automatyczna ewolucja parametrów

3. **Kontrola**
   ```bash
   # Zatrzymaj
   curl -X POST .../auto-train/stop

   # Wznów
   curl -X POST .../auto-train/start

   # Force retrain
   curl -X POST .../auto-train/trigger
   ```

## 🔧 Troubleshooting

### Problem: Auto-training nie startuje
```bash
# Sprawdź czy Celery beat działa
docker-compose logs beat

# Sprawdź status
curl .../auto-train/status
```

### Problem: Modele się nie trenują
```bash
# Sprawdź logi workera
docker-compose logs worker | tail -100

# Sprawdź czy są dane
docker-compose exec db psql -U traderai -d traderai -c \
  "SELECT COUNT(*) FROM ohlcv WHERE symbol='BTC/USDT';"
```

### Problem: Mało sygnałów
```bash
# Obniż MIN_NET_PROFIT_PCT w .env
MIN_NET_PROFIT_PCT=0.8  # Było 1.0

# Lub obniż MIN_CONFIDENCE_THRESHOLD
MIN_CONFIDENCE_THRESHOLD=0.48  # Było 0.50

# Restart API
docker-compose restart api
```

## 📈 Oczekiwane rezultaty

### Po Quick Training (2-3h):
- ✅ Model gotowy do generowania sygnałów
- ✅ Accuracy ~55-60%
- ✅ 2-4 sygnały dziennie na symbol

### Po Full Training (3 dni):
- ✅ Model zoptymalizowany
- ✅ Accuracy 60-65%
- ✅ 3-6 sygnałów dziennie na symbol

### Po kilku cyklach ewolucji (7-14 dni):
- ✅ Parametry dostosowane do rynku
- ✅ Accuracy 62-68%
- ✅ 4-8 sygnałów dziennie na symbol
- ✅ Min 1% zwrot po kosztach

## 🚨 Ważne uwagi

1. **Nie przerywaj pierwszego quick training** - Poczekaj aż się skończy (2-3h)
2. **Monitor resource usage** - Training konsumuje CPU/RAM
3. **Backup bazy przed migracją**
4. **Testy przed produkcją** - Użyj `/auto-train/trigger` do testów

## 📝 Następne kroki (opcjonalne ulepszenia)

1. **Multi-timeframe auto-training** - Trenuj na różnych timeframe'ach
2. **A/B testing modeli** - Deploy dwóch modeli i porównaj wyniki
3. **Alert system** - Powiadomienia gdy model się degraduje
4. **Web UI** - Panel do kontroli auto-training przez przeglądarkę

---

**System jest gotowy! 🎉**

Uruchom migrację i POST /auto-train/start aby zacząć.
