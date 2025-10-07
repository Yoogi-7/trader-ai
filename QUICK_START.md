# ⚡ Quick Start - Auto-Training System

## 🎯 Uruchom w 3 krokach

### 1️⃣ Włącz Auto-Training

```bash
curl -X POST http://localhost:8000/api/v1/auto-train/start \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["BTC/USDT", "ETH/USDT", "BNB/USDT"],
    "timeframe": "15m",
    "quick_start": true
  }'
```

**Odpowiedź:**
```json
{
  "status": "started",
  "symbols": ["BTC/USDT", "ETH/USDT", "BNB/USDT"],
  "timeframe": "15m",
  "quick_mode": true,
  "message": "Auto-training started successfully. Initial training triggered."
}
```

---

### 2️⃣ Sprawdź Status (co 30 min)

```bash
# Status auto-training
curl http://localhost:8000/api/v1/auto-train/status

# Training jobs
curl http://localhost:8000/api/v1/train/jobs | jq '.[:3]'
```

**Przykładowa odpowiedź:**
```json
{
  "enabled": true,
  "symbols": ["BTC/USDT", "ETH/USDT", "BNB/USDT"],
  "timeframe": "15m",
  "quick_mode": true,
  "last_updated": "2025-10-07T07:30:00"
}
```

---

### 3️⃣ Monitoruj Postęp w Bazie

```bash
docker-compose exec -T db psql -U traderai -d traderai << 'EOF'
SELECT
    symbol,
    status,
    ROUND(progress_pct::numeric, 1) as progress,
    current_fold,
    total_folds,
    ROUND(avg_roc_auc::numeric, 3) as auc,
    to_char(updated_at, 'HH24:MI') as time
FROM training_jobs
WHERE status IN ('training', 'completed')
ORDER BY updated_at DESC
LIMIT 5;
EOF
```

---

## 📊 Co się dzieje w tle?

### Timeline:

**0:00** - Start auto-training
```
✓ Quick training triggered (BTC, ETH, BNB)
✓ Test: 14 dni, Train: 90 dni
```

**0:30-3:00** - Quick Training
```
⏳ BTC/USDT: Training... (progress: 45%)
⏳ ETH/USDT: Training... (progress: 38%)
⏳ BNB/USDT: Training... (progress: 42%)
```

**3:00** - Quick Training Complete
```
✅ BTC/USDT model ready (AUC: 0.58, Accuracy: 57%)
✅ ETH/USDT model ready (AUC: 0.61, Accuracy: 59%)
✅ BNB/USDT model ready (AUC: 0.56, Accuracy: 55%)
✓ Signals generation started!
```

**15:00** - First Full Retraining (12h later)
```
🔄 Full training started (Test: 30d, Train: 180d)
📈 Parameters evolved based on quick training results
```

---

## 🎛️ Monitoring Dashboards

### Panel Admin

```bash
# Odrzucone sygnały (ostatnie 24h)
curl http://localhost:8000/api/v1/system/rejected-signals?hours=24 \
  | jq '[.[] | {symbol, reason: .rejection_reason, time: .created_at}] | .[:5]'
```

**Output:**
```json
[
  {
    "symbol": "BTC/USDT",
    "reason": "Failed risk filters: profit",
    "time": "2025-10-07T06:45:23"
  },
  ...
]
```

### System Status

```bash
curl http://localhost:8000/api/v1/system/status | jq '.'
```

**Output:**
```json
{
  "active_models": 3,
  "total_signals": 47,
  "win_rate": 0.58,
  "avg_net_profit_pct": 2.3,
  "total_net_profit_usd": 1247.65
}
```

---

## 🔧 Kontrola

### Zatrzymaj Auto-Training

```bash
curl -X POST http://localhost:8000/api/v1/auto-train/stop
```

### Wznów

```bash
curl -X POST http://localhost:8000/api/v1/auto-train/start \
  -d '{"quick_start": false}'  # Skip quick mode
```

### Wymuś Retraining

```bash
curl -X POST http://localhost:8000/api/v1/auto-train/trigger
```

---

## 📈 Oczekiwane Wyniki

### Quick Training (2-3h):
- ✅ Sygnały: 2-4/dzień na symbol
- ✅ Accuracy: 55-60%
- ✅ Zwrot: 1-2% netto

### Po ewolucji (7 dni):
- ✅ Sygnały: 4-8/dzień na symbol
- ✅ Accuracy: 60-68%
- ✅ Zwrot: 1-3% netto

---

## 🚨 Troubleshooting

### Brak sygnałów po 3h?

```bash
# 1. Sprawdź czy training się zakończył
curl http://localhost:8000/api/v1/train/jobs | jq '.[0] | {status, progress_pct}'

# 2. Sprawdź odrzucone sygnały
curl http://localhost:8000/api/v1/system/rejected-signals?hours=1

# 3. Sprawdź logi
docker-compose logs worker --tail=50 | grep -E "Signal|Training"
```

### Training trwa zbyt długo?

```sql
-- Sprawdź progress w bazie
docker-compose exec db psql -U traderai -d traderai -c \
  "SELECT symbol, current_fold, total_folds, progress_pct
   FROM training_jobs
   WHERE status='training';"
```

**Normalne czasy:**
- Quick mode: 2-3h (14/90 dni)
- Full mode: 12-24h (30/180 dni)

---

## ✅ Checklist Deployment

- [x] Migracja wykonana (`auto_training_config` table)
- [x] Aplikacja zrestartowana
- [x] Endpoint `/auto-train/start` działa
- [x] Endpoint `/system/rejected-signals` działa
- [x] Celery worker widzi `training.auto_train` task
- [x] Celery beat schedule zawiera auto-train co 12h
- [x] Performance tracking cleanup działa

---

**🎉 System gotowy do użycia!**

Uruchom auto-training powyższym poleceniem i poczekaj 2-3h na pierwsze sygnały.
