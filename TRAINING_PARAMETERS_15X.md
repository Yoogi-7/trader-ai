# Training Parameters Increased 15x

## Date: 2025-10-05

## New Parameters (15x Increase)

### Previous Settings:
```python
num_boost_round=100
early_stopping_rounds=10
log_evaluation=25
```

### New Settings (15x):
```python
num_boost_round=1500        # 100 × 15 = 1500
early_stopping_rounds=150   # 10 × 15 = 150
log_evaluation=375          # 25 × 15 = 375
```

## Expected Impact

### Training Time Per Fold:
- **Previous**: ~60 seconds per fold
- **New**: ~15-20 minutes per fold (15-20x slower)

### Total Training Time Per Symbol:
- **POL/USDT** (6 folds): 
  - Previous: 6 minutes
  - New: **1.5-2 hours**

- **BTC/USDT** (67 folds):
  - Previous: 67 minutes
  - New: **17-22 hours** 🚨

- **ETH/USDT** (65 folds):
  - Previous: 65 minutes
  - New: **16-21 hours** 🚨

- **DOGE/USDT** (57 folds):
  - Previous: 57 minutes
  - New: **14-19 hours** 🚨

## Expected Model Quality Improvement

### Realistic Expectations:
- **Current AUC**: ~0.48-0.50 (below random)
- **Expected with 1500 iterations**: 0.52-0.58 (5-15% improvement)
- **Best case**: 0.60-0.65 (if features are good)
- **Worst case**: Still ~0.50 (if features are bad)

### Why This Might Help:
1. ✅ More iterations allow complex pattern learning
2. ✅ Early stopping at 150 rounds gives model more patience
3. ✅ May find better local optimum in parameter space
4. ✅ Better gradient boosting convergence

### Why This Might NOT Help:
1. ❌ If features are not predictive, more iterations won't help
2. ❌ If labels are noisy, model will overfit
3. ❌ If data quality is poor, no amount of training helps
4. ❌ Diminishing returns after ~300-500 iterations

## Monitoring

### Check Training Progress:
```bash
# Check database progress
docker-compose exec db psql -U traderai -d traderai -c "SELECT symbol, current_fold, total_folds, ROUND(progress_pct::numeric, 1) as progress FROM training_jobs WHERE status = 'training';"

# Check worker logs
docker-compose logs worker --tail=50 | grep -E "Training Progress|OOS AUC|ensemble completed"

# Check active tasks
docker-compose exec worker celery -A apps.ml.worker inspect active
```

### Key Metrics to Watch:
1. **OOS AUC** (Out-of-Sample Area Under Curve)
   - Below 0.50: Worse than random ❌
   - 0.50-0.55: Barely better than random ⚠️
   - 0.55-0.60: Decent predictive power ✅
   - 0.60-0.65: Good predictive power ✅✅
   - Above 0.65: Excellent predictive power ✅✅✅

2. **Early Stopping Behavior**
   - If stops at round 50-100: Parameters were too high
   - If stops at round 200-500: Good balance
   - If runs full 1500 rounds: May need more iterations OR overfitting

3. **Training vs Validation Gap**
   - Small gap: Good generalization
   - Large gap: Overfitting (reduce iterations)

## Estimated Completion Times

Starting at: 20:16 (2025-10-05)

### With 3 Concurrent Workers:
- **POL/USDT**: ~22:00 (2 hours)
- **DOGE/USDT**: ~10:00 next day (14 hours)
- **DOT/USDT**: ~12:00 next day (16 hours)
- **All symbols** (12 total): ~3-4 days

## Recommendation for Future

If after this training run:
- **AUC < 0.55**: Reduce to 500 iterations, focus on feature engineering
- **AUC 0.55-0.60**: Keep 1500 iterations for production
- **AUC > 0.60**: Consider increasing to 2000-3000 for maximum quality

## Rollback Plan

If training is too slow or not improving:
```bash
# Stop worker
docker-compose stop worker

# Edit apps/ml/models.py
# Change num_boost_round back to 200-300

# Restart worker
docker-compose start worker
```

Optimal balance for most cases: **num_boost_round=300, early_stopping=30**
