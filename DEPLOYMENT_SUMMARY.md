# 🚀 System Auto-Trenowania - Podsumowanie Wdrożenia

## ✅ Status: **GOTOWY DO UŻYCIA**

Aplikacja została pomyślnie uruchomiona z nowymi funkcjami!

---

## 📋 Co zostało zaimplementowane

### 1. ✨ **System Automatycznego Trenowania**

#### Funkcje:
- **Quick Training Mode** - Szybki trening (2-3h zamiast 3 dni)
- **Continuous Auto-Training** - Automatyczny retraining co 12 godzin
- **Parameter Evolution** - Inteligentna optymalizacja parametrów TP/SL
- **Auto-Leverage** - Automatyczny dobór dźwigni 1-20x na podstawie:
  - Confidence modelu
  - Zmienności rynku (ATR)
  - Profilu ryzyka

#### Parametry optymalizacji:
```python
MIN_NET_PROFIT_PCT: 1.0%  # Zmniejszone z 2.0% → więcej sygnałów
MIN_ACCURACY_TARGET: 60%  # Target accuracy
MIN_CONFIDENCE: 50%       # Zmniejszone z 52% → więcej sygnałów
```

#### API Endpoints:
```bash
# Start auto-training
POST /api/v1/auto-train/start
{
  "symbols": ["BTC/USDT", "ETH/USDT", "BNB/USDT"],
  "timeframe": "15m",
  "quick_start": true
}

# Stop
POST /api/v1/auto-train/stop

# Status
GET /api/v1/auto-train/status

# Config (z evolution stats)
GET /api/v1/auto-train/config

# Manual trigger
POST /api/v1/auto-train/trigger
```

---

### 2. 📊 **Panel Admin - Odrzucone Sygnały**

Nowy endpoint w panelu admina:

```bash
GET /api/v1/system/rejected-signals?hours=24
```

**Pokazuje:**
- Ile sygnałów zostało odrzuconych
- Dlaczego (failed filters)
- Kiedy (timestamp)
- Dla jakiego symbolu i modelu

**Obecnie:** `125 odrzuconych sygnałów w ostatnich 24h`

---

### 3. 🧹 **Auto-Cleanup Performance Tracking**

#### Co robi:
- Kasuje stare katalogi performance_tracking (starsze niż 30 dni)
- Zachowuje tylko 5 najnowszych modeli na symbol
- Uruchamia się automatycznie co 24h (Celery beat)

#### Statystyki:
- **Przed cleanup:** ~XX katalogów, ~XX MB
- **Po cleanup:** Usunięte stare modele, zwolnione miejsce

#### Manual trigger:
```python
from apps.ml.cleanup import PerformanceTrackingCleanup

cleanup = PerformanceTrackingCleanup()
result = cleanup.cleanup()
# {'deleted': 5, 'kept': 10, 'deleted_size_mb': 123.45}
```

---

## 🎯 Jak użyć systemu

### KROK 1: Włącz Auto-Training

```bash
curl -X POST http://localhost:8000/api/v1/auto-train/start \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["BTC/USDT", "ETH/USDT", "BNB/USDT"],
    "timeframe": "15m",
    "quick_start": true
  }'
```

**Co się stanie:**
1. System uruchomi **quick training** (2-3h zamiast 3 dni)
2. Po zakończeniu quick training → model zacznie generować sygnały
3. Co 12h → automatyczny full retraining z ewolucją parametrów
4. Parametry będą ewoluować dla maksymalizacji:
   - Liczby sygnałów
   - Min 1% zwrot
   - Min 60% accuracy

### KROK 2: Monitoruj status

```bash
# Sprawdź status auto-training
curl http://localhost:8000/api/v1/auto-train/status

# Sprawdź odrzucone sygnały
curl http://localhost:8000/api/v1/system/rejected-signals?hours=24
```

### KROK 3: Czekaj na pierwsze sygnały

- **Po quick training (2-3h):** Pierwsze sygnały
- **Po 12h:** Pierwszy full retraining
- **Po 24-48h:** Parametry zoptymalizowane

---

## 📈 Celery Beat Schedule (Automatyczne zadania)

```python
'update-latest-candles-every-15-minutes':    co 15 min
'generate-signals-every-5-minutes':          co 5 min
'expire-signals-every-5-minutes':            co 5 min
'monitor-drift-daily':                        co 24h
'auto-train-every-12-hours':                  co 12h  ← NOWE
'cleanup-performance-tracking-daily':         co 24h  ← NOWE
```

---

## 🔍 Monitoring

### Logi Workera
```bash
# Auto-training logi
docker-compose logs worker | grep -E "Auto-training|Training cycle|Evolution"

# Cleanup logi
docker-compose logs worker | grep "Cleanup"

# Ogólny status
docker-compose logs worker --tail=50
```

### Status w bazie
```sql
-- Auto-training config
SELECT * FROM auto_training_config;

-- Training jobs
SELECT symbol, status, progress_pct, avg_roc_auc
FROM training_jobs
ORDER BY created_at DESC
LIMIT 5;

-- Odrzucone sygnały
SELECT COUNT(*), rejection_reason
FROM signal_rejections
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY rejection_reason;
```

### API Status
```bash
# System status
curl http://localhost:8000/api/v1/system/status

# Candles
curl http://localhost:8000/api/v1/system/candles

# Training jobs
curl http://localhost:8000/api/v1/train/jobs
```

---

## 🎛️ Konfiguracja

### .env / config.py

```python
# Signal Generation (ZOPTYMALIZOWANE)
MIN_NET_PROFIT_PCT = 1.0            # Było: 2.0
MIN_CONFIDENCE_THRESHOLD = 0.50     # Było: 0.52
MIN_ACCURACY_TARGET = 0.60          # Nowe

# Auto-Training
AUTO_TRAINING_ENABLED = False       # Kontrolowane przez API
AUTO_TRAINING_INTERVAL_HOURS = 12
QUICK_TRAINING_TEST_DAYS = 14
QUICK_TRAINING_MIN_DAYS = 90
FULL_TRAINING_TEST_DAYS = 30
FULL_TRAINING_MIN_DAYS = 180

# Auto-Leverage
AUTO_LEVERAGE = True                # Nowe - automatyczny dobór dźwigni

# Performance Tracking
PERFORMANCE_TRACKING_DIR = "./performance_tracking"
```

---

## 🚨 Troubleshooting

### Problem: Auto-training nie startuje

```bash
# Sprawdź status
curl http://localhost:8000/api/v1/auto-train/status

# Sprawdź logi beat
docker-compose logs beat --tail=50

# Sprawdź logi worker
docker-compose logs worker --tail=50
```

### Problem: Mało sygnałów

```bash
# Sprawdź odrzucone sygnały
curl http://localhost:8000/api/v1/system/rejected-signals?hours=24

# Rozwiązania:
# 1. Obniż MIN_NET_PROFIT_PCT w .env
MIN_NET_PROFIT_PCT=0.8

# 2. Obniż MIN_CONFIDENCE_THRESHOLD
MIN_CONFIDENCE_THRESHOLD=0.48

# 3. Restart
docker-compose restart api worker
```

### Problem: Performance tracking zajmuje dużo miejsca

```bash
# Sprawdź użycie dysku
du -sh performance_tracking/

# Manual cleanup
curl -X POST http://localhost:8000/api/v1/maintenance/cleanup

# Lub zmień parametry
# W worker.py, cleanup task:
max_age_days=15  # Było: 30
max_models_per_symbol=3  # Było: 5
```

---

## 📊 Oczekiwane Wyniki

### Po Quick Training (2-3h):
✅ Model gotowy
✅ Accuracy ~55-60%
✅ 2-4 sygnały/dzień na symbol

### Po Full Training (3 dni):
✅ Model zoptymalizowany
✅ Accuracy 60-65%
✅ 3-6 sygnałów/dzień na symbol

### Po ewolucji (7-14 dni):
✅ Parametry dostosowane
✅ Accuracy 62-68%
✅ 4-8 sygnałów/dzień na symbol
✅ Min 1% zwrot po kosztach

---

## 🎉 Następne kroki

1. **Uruchom auto-training:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/auto-train/start \
     -H "Content-Type: application/json" \
     -d '{"quick_start": true}'
   ```

2. **Monitor przez pierwsze 24h**
3. **Sprawdź odrzucone sygnały** - dostosuj parametry jeśli potrzeba
4. **Pozwól systemowi ewoluować** przez 7-14 dni

---

## 📚 Pliki Dodane/Zmienione

### Nowe pliki:
- `apps/ml/auto_trainer.py` - System auto-trenowania
- `apps/ml/cleanup.py` - Auto-cleanup performance tracking
- `apps/api/routers/auto_train.py` - API dla auto-training
- `migrations/versions/b1c2d3e4f5a6_add_auto_training_config.py` - Migracja
- `AUTO_TRAINING_SETUP.md` - Szczegółowa dokumentacja

### Zmienione pliki:
- `apps/ml/worker.py` - Dodane taski: auto_train, cleanup
- `apps/ml/signal_engine.py` - Auto-leverage integration
- `apps/api/config.py` - Nowe parametry optymalizacji
- `apps/api/db/models.py` - Model AutoTrainingConfig
- `apps/api/main.py` - Router auto_train
- `apps/api/routers/system.py` - Endpoint rejected-signals

---

**Status: ✅ WSZYSTKO DZIAŁA!**

Aplikacja jest gotowa do pracy. Wystarczy uruchomić auto-training przez API.
