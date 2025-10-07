# ✅ Harmonogram Auto-Trainingu Zaktualizowany

## 📅 Nowy Harmonogram

**Auto-training uruchamia się teraz RAZ W TYGODNIU (co 7 dni)**

### Zmienione parametry:

#### Celery Beat Schedule:
```python
'auto-train-weekly': {
    'task': 'training.auto_train',
    'schedule': 604800.0,  # 7 days (1 week)
}
```

**Było:** `co 12 godzin` (43200.0s)
**Jest:** `co 7 dni` (604800.0s)

#### Config.py:
```python
AUTO_TRAINING_INTERVAL_DAYS = 7  # Retrain co tydzień
```

**Było:** `AUTO_TRAINING_INTERVAL_HOURS = 12`
**Jest:** `AUTO_TRAINING_INTERVAL_DAYS = 7`

#### Auto Trainer Logic:
```python
# Model jest retrenowany jeśli ma 7+ dni
if age_days >= 7:
    logger.info("Triggering weekly retrain")
    return True
```

---

## 🔄 Jak to działa teraz

### Timeline:

**Dzień 0** - Włączenie auto-training:
```bash
POST /api/v1/auto-train/start
```
- ✅ Quick training (2-3h)
- ✅ Model gotowy, sygnały generowane

**Dzień 7** - Pierwszy weekly retrain:
- 🔄 Automatyczny full training
- 📈 Parametry ewoluują
- ✅ Nowy model wdrożony

**Dzień 14** - Drugi weekly retrain:
- 🔄 Kolejny full training
- 📈 Dalsza optymalizacja
- ✅ Model coraz lepszy

**Etc...**

---

## 📊 Celery Beat Schedule (Wszystkie taski)

```python
✓ update-latest-candles           co 15 min
✓ generate-signals                 co 5 min
✓ expire-signals                   co 5 min
✓ monitor-drift                    co 24h (1 dzień)
✓ auto-train-weekly                co 7 dni (1 tydzień)  ← ZMIENIONE
✓ cleanup-performance-tracking     co 24h (1 dzień)
```

---

## 🎯 Zalety Weekly Schedule

### 1. **Mniej obciążenia serwera**
- Training konsumuje CPU/RAM
- Weekly = więcej zasobów dla signal generation
- Brak ciągłych retrenowań

### 2. **Więcej danych dla ewolucji**
- 7 dni działania modelu = więcej sample'ów
- Lepsza ocena skuteczności parametrów
- Bardziej przemyślane zmiany

### 3. **Stabilność modeli**
- Model działa przez tydzień bez zmian
- Łatwiejsze śledzenie performance
- Mniejsze ryzyko degradacji

### 4. **Optymalne timing**
- Rynek ma różne cykle (np. weekend)
- 7 dni = pełny cykl tygodniowy
- Lepsze uśrednienie wyników

---

## 🚀 Manual Override

Jeśli chcesz wymusić retraining przed upływem tygodnia:

```bash
# Wymuś natychmiastowy retraining
curl -X POST http://localhost:8000/api/v1/auto-train/trigger
```

To uruchomi training niezależnie od harmonogramu.

---

## 📝 Aktualizacje w dokumentacji

Zaktualizowane pliki:
- ✅ `apps/ml/worker.py` - Schedule: 604800s (7 dni)
- ✅ `apps/api/config.py` - INTERVAL_DAYS = 7
- ✅ `apps/ml/auto_trainer.py` - Logic: age >= 7 days
- ✅ `AUTO_TRAINING_SETUP.md` - Dokumentacja
- ✅ `DEPLOYMENT_SUMMARY.md` - Podsumowanie
- ✅ `QUICK_START.md` - Quick start guide

---

## ✅ Status: WDROŻONE

```bash
# Sprawdź status
curl http://localhost:8000/api/v1/auto-train/status

# Worker i beat zrestartowane
docker-compose ps
```

Wszystko działa z nowym harmonogramem weekly (co 7 dni)!
