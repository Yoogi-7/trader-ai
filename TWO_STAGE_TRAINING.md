# Two-Stage Training System

**Quick Validation → Full Production Training**

---

## 🎯 Overview

The system now supports **two-stage training**:

1. **Stage 1: Quick Validation** (3-4 hours) - Fast feedback on hyperparameters and improvements
2. **Stage 2: Full Training** (35-45 hours) - Complete production-ready model

This approach allows you to:
- ✅ Validate improvements quickly before committing to full training
- ✅ Catch issues early (bad hyperparameters, data problems)
- ✅ Save time by not running 40-hour trainings that fail
- ✅ Iterate faster on improvements

---

## 📊 Training Modes Comparison

| Aspect | Quick Training | Full Training |
|--------|----------------|---------------|
| **Duration** | 3-4 hours | 35-45 hours |
| **Folds** | ~5 folds | ~45 folds |
| **Test Period** | 60 days (2 months) | 21 days (3 weeks) |
| **Train Window** | Fixed (last 6 months) | Expanding (all data) |
| **Min Train Data** | 180 days | 120 days |
| **Purpose** | Validation | Production |
| **Use Case** | Test improvements | Deploy to production |

---

## 🚀 Quick Start

### Option 1: Quick Training Only

Test your improvements fast:

```bash
cd /root/apps/traderai
./scripts/train_quick.sh BTC/USDT M15
```

**Monitors in real-time**:
```bash
docker logs traderai-worker-training2 -f | grep "OOS Test Metrics"
```

**Expected output after 3-4 hours**:
```
Fold 1/5: accuracy=62.5%, recall=45%, roc_auc=65.2%
Fold 2/5: accuracy=61.8%, recall=42%, roc_auc=64.1%
...
Average: accuracy=62%, recall=44%, roc_auc=64.5%
```

### Option 2: Full Training Only

When you're confident in your setup:

```bash
./scripts/train_full.sh BTC/USDT M15
```

Takes 35-45 hours but produces production model.

### Option 3: Sequential (Recommended!)

Best approach - validates first, then trains:

```bash
./scripts/train_sequential.sh BTC/USDT M15
```

**Workflow**:
1. Runs quick training (3-4h)
2. Shows results and asks for confirmation
3. If approved, runs full training (35-45h)
4. Total: ~40-50 hours with early validation

---

## 🔧 Manual API Usage

### Quick Training

```bash
curl -X POST http://localhost:8000/api/training/start \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "timeframe": "M15",
    "training_mode": "quick",
    "test_period_days": 60,
    "min_train_days": 180,
    "use_expanding_window": false
  }'
```

### Full Training

```bash
curl -X POST http://localhost:8000/api/training/start \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "timeframe": "M15",
    "training_mode": "full",
    "test_period_days": 21,
    "min_train_days": 120,
    "use_expanding_window": true
  }'
```

---

## 📊 Monitoring Progress

### Check Job Status

```bash
docker exec traderai-db psql -U traderai -d traderai -c \
  "SELECT symbol, status, progress_pct, accuracy, hit_rate_tp1, avg_roc_auc,
   elapsed_seconds/3600 as hours_elapsed
   FROM training_jobs
   ORDER BY created_at DESC LIMIT 5;"
```

### Watch Real-Time Metrics

```bash
# Training Worker 2
docker logs traderai-worker-training2 -f | grep -E "(Fold|accuracy|recall)"

# Training Worker 3
docker logs traderai-worker-training3 -f | grep -E "(Fold|accuracy|recall)"
```

### Check Fold Details

```bash
docker logs traderai-worker-training2 2>&1 | grep "OOS Test Metrics" | tail -20
```

---

## 🎓 How It Works

### Quick Training (3-4 hours)

**Configuration**:
```python
training_mode='quick'
test_period_days=60      # 2 months per fold (larger chunks)
min_train_days=180       # Start with 6 months
use_expanding_window=False  # Fixed window for speed
```

**Data Usage**:
- Uses **last 12 months** of data only
- Creates **~5 folds**:
  - Fold 1: Train on months 1-6, test on months 7-8
  - Fold 2: Train on months 1-6, test on months 9-10
  - Fold 3: Train on months 1-6, test on months 11-12
  - Fold 4: Train on months 3-8, test on months 9-10
  - Fold 5: Train on months 5-10, test on months 11-12

**Speed**:
- ~45 minutes per fold
- Total: 3-4 hours

### Full Training (35-45 hours)

**Configuration**:
```python
training_mode='full'
test_period_days=21      # 3 weeks per fold (granular)
min_train_days=120       # Start with 4 months
use_expanding_window=True  # Growing window
```

**Data Usage**:
- Uses **ALL available data** (5+ years)
- Creates **~45 folds**:
  - Fold 1: Train on 4 months, test on 3 weeks
  - Fold 2: Train on 4.7 months, test on 3 weeks
  - Fold 3: Train on 5.4 months, test on 3 weeks
  - ...
  - Fold 45: Train on 5.5 years, test on 3 weeks

**Speed**:
- ~50-60 minutes per fold
- Total: 35-45 hours

---

## 🎯 When to Use Which Mode

### Use Quick Training When:

✅ Testing new hyperparameters
✅ Validating feature engineering changes
✅ Testing labeling strategy adjustments
✅ Debugging training pipeline issues
✅ Need fast feedback (same day)

### Use Full Training When:

✅ Deploying to production
✅ Creating final model for live trading
✅ Need maximum accuracy and robustness
✅ After quick validation confirms improvements
✅ Can afford 35-45 hour wait

### Use Sequential Training When:

✅ **Recommended default approach**
✅ Making significant changes
✅ Want safety net before full training
✅ Need validation before committing resources

---

## 📈 Expected Results

### Quick Training Targets

Based on improved hyperparameters:

| Symbol | Accuracy | Recall | ROC AUC |
|--------|----------|--------|---------|
| ETH/USDT | 68-70% | 40-50% | 64-66% |
| BTC/USDT | 60-63% | 35-45% | 61-64% |
| BNB/USDT | 61-63% | 38-48% | 63-66% |

If quick training shows these metrics, **proceed to full training**.

### Full Training Targets

After 45 folds:

| Symbol | Accuracy | Recall | ROC AUC |
|--------|----------|--------|---------|
| ETH/USDT | 68-70% | 45-60% | 66-68% |
| BTC/USDT | 62-65% | 40-55% | 62-65% |
| BNB/USDT | 62-64% | 42-55% | 65-68% |

---

## ⚠️ Important Notes

### Resource Usage

- **Quick Training**: 1 worker, 4-8GB RAM
- **Full Training**: 1 worker, 8-16GB RAM
- Can run **3 symbols in parallel** on different workers

### Stopping Training

```bash
# Stop current training job
docker exec traderai-db psql -U traderai -d traderai -c \
  "UPDATE training_jobs SET status = 'cancelled' WHERE status = 'training';"

# Restart worker to stop immediately
docker restart traderai-worker-training2
```

### Disk Space

- **Quick Training**: ~500MB per symbol
- **Full Training**: ~2-3GB per symbol
- Clean up old models regularly

---

## 🔄 Migration from Old Training

### Before (Single Long Training)

```bash
# Start training - wait 60-70 hours
# If something wrong -> restart and wait another 60-70 hours
```

### After (Two-Stage Training)

```bash
# Stage 1: Quick validation - wait 3-4 hours
# Check results -> adjust if needed
# Stage 2: Full training - wait 35-45 hours
# Total: ~40-50 hours with validation
```

**Time Saved**:
- If quick training shows problems: **Save 35-45 hours**
- If quick training passes: **Same total time, but with validation**

---

## 📝 Code Changes

### Modified Files

1. **apps/ml/training.py**
   - Added `training_mode` parameter
   - Auto-adjusts fold configuration based on mode
   - Logs mode selection clearly

2. **apps/ml/worker.py**
   - Added `training_mode` to Celery task
   - Passes mode through pipeline

3. **scripts/** (new)
   - `train_quick.sh` - Quick training
   - `train_full.sh` - Full training
   - `train_sequential.sh` - Two-stage training

---

## 🚀 Recommended Workflow

### Initial Setup (After Improvements)

```bash
# 1. Test quick training on one symbol
./scripts/train_quick.sh BTC/USDT M15

# 2. Wait 3-4 hours and check results

# 3. If good, run full training on all symbols
./scripts/train_full.sh BTC/USDT M15 &
./scripts/train_full.sh ETH/USDT M15 &
./scripts/train_full.sh BNB/USDT M15 &
```

### Regular Updates (With Sequential)

```bash
# Run sequential for each symbol
./scripts/train_sequential.sh BTC/USDT M15
./scripts/train_sequential.sh ETH/USDT M15
./scripts/train_sequential.sh BNB/USDT M15
```

---

## 🎯 Success Criteria

### Quick Training Should Show:

- ✅ Recall > 35% (up from 5-15% on ETH)
- ✅ Accuracy > 60%
- ✅ ROC AUC > 61%
- ✅ F1 Score > 0.45
- ✅ No training errors/crashes

If **ALL** criteria met → Proceed to full training
If **ANY** criteria fail → Debug and fix before full training

---

## 📖 See Also

- [TRAINING_IMPROVEMENTS.md](TRAINING_IMPROVEMENTS.md) - All quality improvements
- [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) - System architecture
- Training logs: `docker logs traderai-worker-training2`

---

**Status**: ✅ Implemented and ready to use

**Next Steps**: Run `./scripts/train_sequential.sh BTC/USDT M15` to start validation
