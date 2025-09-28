import useSWR from 'swr';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { fetcher } from '../api';

interface JournalPoint {
  ts: number;
  equity: number;
}

interface JournalTradeRef {
  symbol: string;
  ts: number;
  pnl: number;
  direction: string;
  market_regime?: string | null;
  sentiment_rating?: number | null;
  ai_summary?: string | null;
}

interface JournalRegimeEntry {
  regime: string;
  trades: number;
  win_rate: number;
  pnl: number;
}

interface JournalMetrics {
  total_trades: number;
  win_rate: number;
  avg_pnl: number;
  max_drawdown: number;
  cumulative_pnl: number;
  best_trade: JournalTradeRef | null;
  worst_trade: JournalTradeRef | null;
}

interface JournalSentimentSummary {
  avg_rating?: number | null;
  positive_share?: number | null;
  negative_share?: number | null;
}

interface JournalResponse {
  equity_curve: JournalPoint[];
  metrics: JournalMetrics;
  recent_mistakes: JournalTradeRef[];
  regime_breakdown: JournalRegimeEntry[];
  sentiment_summary: JournalSentimentSummary;
}

function formatDate(ts: number) {
  return new Date(ts).toLocaleString('pl-PL', { hour12: false });
}

export const TradingJournal: React.FC = () => {
  const { data, error } = useSWR<JournalResponse>('/journal', fetcher, { refreshInterval: 60_000 });

  if (error) {
    return <div className="text-sm text-red-600">Nie udało się załadować dziennika.</div>;
  }

  if (!data) {
    return <div className="text-sm text-slate-500">Ładowanie dziennika…</div>;
  }

  const equityData = data.equity_curve.map((p) => ({
    ts: formatDate(p.ts),
    equity: Number(p.equity.toFixed(2)),
  }));

  return (
    <div className="space-y-4">
      <div className="h-60">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={equityData} margin={{ top: 10, right: 16, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="ts" tick={{ fontSize: 10 }} hide={equityData.length > 60} angle={-30} textAnchor="end" />
            <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} />
            <Tooltip formatter={(value: number) => `${value.toFixed(2)} USDT`} labelFormatter={(label) => label} />
            <Line type="monotone" dataKey="equity" stroke="#2563eb" dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid md:grid-cols-3 gap-3 text-sm">
        <div className="rounded-lg border border-slate-200 p-3">
          <div className="text-slate-500">Łączny PnL</div>
          <div className="text-lg font-semibold">{data.metrics.cumulative_pnl.toFixed(2)} USDT</div>
        </div>
        <div className="rounded-lg border border-slate-200 p-3">
          <div className="text-slate-500">Win rate</div>
          <div className="text-lg font-semibold">{(data.metrics.win_rate * 100).toFixed(1)}%</div>
        </div>
        <div className="rounded-lg border border-slate-200 p-3">
          <div className="text-slate-500">Max drawdown</div>
          <div className="text-lg font-semibold">{data.metrics.max_drawdown.toFixed(2)} USDT</div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-3 text-sm">
        <div className="rounded-lg border border-slate-200 p-3">
          <div className="font-semibold mb-2">Najlepszy trade</div>
          {data.metrics.best_trade ? (
            <div className="space-y-1">
              <div>{data.metrics.best_trade.symbol} ({data.metrics.best_trade.direction})</div>
              <div>Zysk: {data.metrics.best_trade.pnl.toFixed(2)} USDT</div>
              {data.metrics.best_trade.market_regime && <div>Regime: {data.metrics.best_trade.market_regime}</div>}
              {typeof data.metrics.best_trade.sentiment_rating === 'number' && (
                <div>Sentiment: {data.metrics.best_trade.sentiment_rating}/100</div>
              )}
            </div>
          ) : (
            <div>Brak danych.</div>
          )}
        </div>
        <div className="rounded-lg border border-slate-200 p-3">
          <div className="font-semibold mb-2">Do poprawy</div>
          {data.recent_mistakes.length > 0 ? (
            <ul className="space-y-2">
              {data.recent_mistakes.map((m, idx) => (
                <li key={idx} className="border border-red-200 rounded-md p-2">
                  <div>{m.symbol} ({m.direction})</div>
                  <div>Strata: {m.pnl.toFixed(2)} USDT</div>
                  {m.market_regime && <div>Regime: {m.market_regime}</div>}
                  {typeof m.sentiment_rating === 'number' && <div>Sentiment: {m.sentiment_rating}/100</div>}
                  {m.ai_summary && (
                    <div className="text-xs text-slate-500 mt-1">
                      {m.ai_summary}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <div>Brak strat do analizy 🎉</div>
          )}
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-3 text-sm">
        <div className="rounded-lg border border-slate-200 p-3">
          <div className="font-semibold mb-2">Regime stats</div>
          {data.regime_breakdown.length > 0 ? (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-slate-500">
                  <th className="py-1">Regime</th>
                  <th className="py-1">Trades</th>
                  <th className="py-1">Win%</th>
                  <th className="py-1">PnL</th>
                </tr>
              </thead>
              <tbody>
                {data.regime_breakdown.map((row) => (
                  <tr key={row.regime}>
                    <td className="py-1">{row.regime}</td>
                    <td className="py-1">{row.trades}</td>
                    <td className="py-1">{(row.win_rate * 100).toFixed(1)}%</td>
                    <td className="py-1">{row.pnl.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div>Jeszcze brak statystyk.</div>
          )}
        </div>
        <div className="rounded-lg border border-slate-200 p-3">
          <div className="font-semibold mb-2">Sentiment insight</div>
          {typeof data.sentiment_summary.avg_rating === 'number' ? (
            <div className="space-y-1">
              <div>Średni rating: {data.sentiment_summary.avg_rating.toFixed(1)} / 100</div>
              {typeof data.sentiment_summary.positive_share === 'number' && (
                <div>Pozytywne sygnały: {(data.sentiment_summary.positive_share * 100).toFixed(1)}%</div>
              )}
              {typeof data.sentiment_summary.negative_share === 'number' && (
                <div>Negatywne sygnały: {(data.sentiment_summary.negative_share * 100).toFixed(1)}%</div>
              )}
            </div>
          ) : (
            <div>Brak danych sentymentu.</div>
          )}
        </div>
      </div>
    </div>
  );
};
