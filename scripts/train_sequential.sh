#!/bin/bash
# Two-stage training: Quick validation followed by full training

set -e

SYMBOL="${1:-BTC/USDT}"
TIMEFRAME="${2:-M15}"

echo "🎯 TWO-STAGE TRAINING FOR $SYMBOL $TIMEFRAME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Stage 1: Quick validation (3-4 hours, ~5 folds)"
echo "Stage 2: Full training (35-45 hours, ~45 folds)"
echo ""

read -p "Start two-stage training? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Training cancelled"
    exit 1
fi

# Stage 1: Quick training
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 STAGE 1: QUICK VALIDATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

./scripts/train_quick.sh "$SYMBOL" "$TIMEFRAME"

echo ""
echo "Waiting for quick training to complete..."
echo "Monitoring logs (Ctrl+C to continue manually)..."
echo ""

# Wait for quick training to complete (check every 5 minutes)
while true; do
    STATUS=$(docker exec traderai-db psql -U traderai -d traderai -t -c \
        "SELECT status FROM training_jobs WHERE symbol = '$SYMBOL' ORDER BY created_at DESC LIMIT 1;" | xargs)

    if [ "$STATUS" = "completed" ]; then
        echo ""
        echo "✅ Quick training completed!"
        break
    elif [ "$STATUS" = "failed" ]; then
        echo ""
        echo "❌ Quick training failed! Check logs:"
        echo "   docker logs traderai-worker-training2 --tail 100"
        exit 1
    fi

    echo "Status: $STATUS - checking again in 5 minutes..."
    sleep 300
done

# Show quick results
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 QUICK TRAINING RESULTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker exec traderai-db psql -U traderai -d traderai -c \
    "SELECT accuracy, hit_rate_tp1, avg_roc_auc FROM training_jobs WHERE symbol = '$SYMBOL' ORDER BY created_at DESC LIMIT 1;"

echo ""
read -p "Results look good? Continue with full training? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Full training cancelled"
    exit 0
fi

# Stage 2: Full training
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 STAGE 2: FULL TRAINING"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

./scripts/train_full.sh "$SYMBOL" "$TIMEFRAME"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ TWO-STAGE TRAINING PIPELINE STARTED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Full training will take 35-45 hours."
echo "You can safely close this terminal."
