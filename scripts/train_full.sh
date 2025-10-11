#!/bin/bash
# Full training script - runs complete production training (35-45 hours)

set -e

SYMBOL="${1:-BTC/USDT}"
TIMEFRAME="${2:-M15}"

echo "📊 Starting FULL training for $SYMBOL $TIMEFRAME"
echo "⏱️  Expected duration: 35-45 hours (~45 folds)"
echo "🎯 This will create a production-ready model"
echo ""

read -p "Are you sure you want to start full training? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Training cancelled"
    exit 1
fi

# Trigger training via API
curl -X POST http://localhost:8000/api/training/start \
  -H "Content-Type: application/json" \
  -d "{
    \"symbol\": \"$SYMBOL\",
    \"timeframe\": \"$TIMEFRAME\",
    \"training_mode\": \"full\",
    \"test_period_days\": 21,
    \"min_train_days\": 120,
    \"use_expanding_window\": true
  }"

echo ""
echo "✅ Full training job submitted!"
echo ""
echo "Monitor progress:"
echo "  docker logs traderai-worker-training2 -f | grep 'OOS Test Metrics'"
echo ""
echo "This will take 35-45 hours. You can safely close this terminal."
