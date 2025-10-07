#!/bin/bash

# Monitor Backfill Progress
# Usage: ./monitor_backfill.sh

echo "📊 BACKFILL PROGRESS MONITOR"
echo "============================"
echo ""

while true; do
  clear
  echo "📊 BACKFILL PROGRESS - $(date '+%Y-%m-%d %H:%M:%S')"
  echo "=================================================="
  echo ""

  # API progress
  echo "🔄 Jobs Status:"
  curl -s http://localhost:8000/api/v1/backfill/jobs | jq -r '.[] | "  \(.symbol): \(.status) - \(.progress_pct | floor)% (\(.candles_fetched) świec)"'

  echo ""
  echo "📈 Database Stats:"

  # Database stats
  docker-compose exec -T db psql -U traderai -d traderai << 'EOF' 2>/dev/null
SELECT
    symbol,
    COUNT(*) as candles,
    to_char(MIN(timestamp), 'YYYY-MM-DD') as oldest,
    to_char(MAX(timestamp), 'YYYY-MM-DD') as newest,
    ROUND(EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) / 86400, 0) as days
FROM ohlcv
GROUP BY symbol
ORDER BY symbol;

SELECT
    '  TOTAL' as info,
    COUNT(*) as candles,
    pg_size_pretty(pg_total_relation_size('ohlcv')) as size
FROM ohlcv;
EOF

  echo ""
  echo "🔄 Odświeżanie za 30 sekund... (Ctrl+C aby zatrzymać)"
  sleep 30
done
