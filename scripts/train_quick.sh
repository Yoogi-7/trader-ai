#!/bin/bash
# Quick training script - runs fast validation training (3-4 hours)

set -e

SYMBOL="${1:-BTC/USDT}"
TIMEFRAME="${2:-M15}"

echo "🚀 Starting QUICK training for $SYMBOL $TIMEFRAME"
echo "⏱️  Expected duration: 3-4 hours (~5 folds)"
echo "📊 This is validation only - use train_full.sh for production model"
echo ""

# Trigger training via API
curl -X POST http://localhost:8000/api/training/start \
  -H "Content-Type: application/json" \
  -d "{
    \"symbol\": \"$SYMBOL\",
    \"timeframe\": \"$TIMEFRAME\",
    \"training_mode\": \"quick\",
    \"test_period_days\": 60,
    \"min_train_days\": 180,
    \"use_expanding_window\": false
  }"

echo ""
echo "✅ Quick training job submitted!"
echo ""
echo "Monitor progress:"
echo "  docker logs traderai-worker-training2 -f | grep 'OOS Test Metrics'"
