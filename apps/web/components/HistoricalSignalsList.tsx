import { useMemo } from 'react'

export interface HistoricalSignal {
  signal_id: string
  symbol: string
  side: string
  entry_price: number
  timeframe?: string
  timestamp: string
  confidence: number
  expected_net_profit_pct: number
  ai_summary?: string
  actual_net_pnl_pct?: number | null
  actual_net_pnl_usd?: number | null
  final_status?: string | null
  duration_minutes?: number | null
  was_profitable?: boolean | null
}

interface HistoricalSignalsListProps {
  signals: HistoricalSignal[]
}

export function HistoricalSignalsList({ signals }: HistoricalSignalsListProps) {
  const rows = useMemo(() => signals ?? [], [signals])

  if (!rows.length) {
    return (
      <div className="bg-gray-700 rounded-lg p-4 text-sm text-gray-300">
        No historical signals available for the selected filters.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {rows.map((signal) => (
        <div key={signal.signal_id} className="bg-gray-700 rounded-lg p-4">
          <div className="grid grid-cols-5 gap-4 mb-3">
            <div>
              <p className="text-xs text-gray-400">Time</p>
              <p className="text-sm">{new Date(signal.timestamp).toLocaleString()}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Symbol</p>
              <p className="text-sm font-bold">
                {signal.symbol}
                {signal.timeframe ? ` (${signal.timeframe})` : ''}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Side</p>
              <span
                className={`px-2 py-1 rounded text-xs ${
                  signal.side === 'LONG' ? 'bg-green-600' : 'bg-red-600'
                }`}
              >
                {signal.side}
              </span>
            </div>
            <div>
              <p className="text-xs text-gray-400">Entry</p>
              <p className="text-sm">${signal.entry_price.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Final Status</p>
              {signal.final_status ? (
                <span
                  className={`px-2 py-1 rounded text-xs ${
                    signal.final_status?.includes('tp') ? 'bg-green-600' :
                    signal.final_status === 'sl_hit' ? 'bg-red-600' :
                    'bg-gray-600'
                  }`}
                >
                  {signal.final_status}
                </span>
              ) : (
                <span className="text-gray-500">Unknown</span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-5 gap-4 mb-3 text-sm">
            <div>
              <p className="text-xs text-gray-400">Expected Profit</p>
              <p className="text-gray-300">{signal.expected_net_profit_pct.toFixed(2)}%</p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Actual %</p>
              <p
                className={`font-bold ${
                  signal.actual_net_pnl_pct === null || signal.actual_net_pnl_pct === undefined
                    ? 'text-gray-400'
                    : signal.actual_net_pnl_pct >= 0
                      ? 'text-green-400'
                      : 'text-red-400'
                }`}
              >
                {signal.actual_net_pnl_pct !== null && signal.actual_net_pnl_pct !== undefined
                  ? `${signal.actual_net_pnl_pct.toFixed(2)}%`
                  : 'N/A'}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Actual $</p>
              <p
                className={`font-bold ${
                  signal.actual_net_pnl_usd === null || signal.actual_net_pnl_usd === undefined
                    ? 'text-gray-400'
                    : signal.actual_net_pnl_usd >= 0
                      ? 'text-green-400'
                      : 'text-red-400'
                }`}
              >
                {signal.actual_net_pnl_usd !== null && signal.actual_net_pnl_usd !== undefined
                  ? `$${signal.actual_net_pnl_usd.toFixed(2)}`
                  : 'N/A'}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Confidence</p>
              <p className="text-gray-300">{(signal.confidence * 100).toFixed(1)}%</p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Duration</p>
              <p className="text-gray-300">
                {signal.duration_minutes !== null && signal.duration_minutes !== undefined
                  ? `${signal.duration_minutes}m`
                  : 'N/A'}
              </p>
            </div>
          </div>

          {signal.ai_summary && (
            <div className="mt-3 p-3 bg-gray-800 rounded border-l-4 border-blue-500">
              <p className="text-xs text-blue-400 font-semibold mb-1">🤖 AI Analysis</p>
              <p className="text-sm text-gray-300">{signal.ai_summary}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
