# ML Training System Optimization

## Date: 2025-10-05

## Problem
- All trainings were stuck at fold 1/X with 5% progress
- System was running too many concurrent processes (8 workers)
- Lack of task prioritization caused deadlocks
- Models were training too long (1000 iterations) without visible progress

## Solution

### 1. Limited Number of Workers
**File:** `docker-compose.yml`
```yaml
command: celery -A apps.ml.worker worker --loglevel=info --concurrency=3 --max-tasks-per-child=1 -Q backfill,training,historical,default
```
- Reduced from 8 → 3 concurrent processes
- Added `--max-tasks-per-child=1` to prevent memory leaks

### 2. Priority Queue System
**File:** `apps/ml/worker.py`

Queues by priority:
1. **backfill** (priority 10) - Fetching exchange data
2. **backfill.update_latest** (priority 9) - Updating fresh data
3. **signals.expire** (priority 8) - Expiring signals
4. **signals.generate** (priority 7) - Generating signals
5. **training** (priority 5) - Training models
6. **drift.monitor** (priority 3) - Monitoring drift
7. **historical** (priority 1) - Generating historical data

Configuration:
```python
task_routes={
    'backfill.execute': {'queue': 'backfill', 'priority': 10},
    'backfill.update_latest': {'queue': 'backfill', 'priority': 9},
    'training.train_model': {'queue': 'training', 'priority': 5},
    'signals.generate_historical': {'queue': 'historical', 'priority': 1},
    ...
},
worker_prefetch_multiplier=1,
worker_max_tasks_per_child=1,
```

### 3. Model Training Optimization
**File:** `apps/ml/models.py`

Training parameter changes:
- **LightGBM:**
  - `num_boost_round`: 1000 → 300
  - `early_stopping`: 50 → 20 rounds
  - `log_evaluation`: 100 → 50

- **XGBoost:**
  - `num_boost_round`: 1000 → 300
  - `early_stopping_rounds`: 50 → 20
  - `verbose_eval`: 100 → 50

### 4. Database Cleanup
Cleaned all tables:
- `training_jobs`
- `model_registry`
- `signals`
- `signal_generation_jobs`
- `backfill_jobs`
- `historical_signal_snapshots`
- `drift_metrics`

Cleaned directories:
- `models/*`
- `performance_tracking/*`

## Task Execution Order

1. **Backfill** - System first fetches and updates exchange data
2. **Training** - After data collection, model training begins
3. **Signals** - Generating signals based on trained models
4. **Historical** - Generating historical data (lowest priority)

## Monitoring

Check queue status:
```bash
docker-compose exec worker celery -A apps.ml.worker inspect active
```

Check training status:
```bash
docker-compose exec db psql -U traderai -d traderai -c "SELECT symbol, status, current_fold, total_folds, progress_pct FROM training_jobs ORDER BY started_at DESC LIMIT 10;"
```

## Expected Results

- Trainings should start after backfill completion
- Maximum 3 concurrent processes
- Each fold should complete in reasonable time (minutes, not hours)
- Progress should be visible in UI
- No deadlocks between tasks
