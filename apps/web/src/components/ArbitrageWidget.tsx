import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';

interface Opportunity {
  symbol: string;
  buy_exchange: string;
  sell_exchange: string;
  buy_price: number;
  sell_price: number;
  spread_pct: number;
  timestamp_ms: number;
}

export const ArbitrageWidget: React.FC = () => {
  const [opps, setOpps] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.scanArbitrage({
        exchanges: ['binance', 'bybit'],
        symbols: ['BTC/USDT', 'ETH/USDT'],
        min_spread_pct: 0.25,
        market_type: 'spot',
      });
      setOpps(res.opportunities);
    } catch (e: any) {
      setError(e.message || 'Błąd skanowania');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 60_000);
    return () => clearInterval(timer);
  }, [refresh]);

  return (
    <div className="space-y-2 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-semibold">Cross-exchange arbitrage</span>
        <button
          className="text-xs px-2 py-1 rounded border border-slate-300 hover:bg-slate-100"
          onClick={refresh}
          disabled={loading}
        >
          {loading ? 'Skanowanie…' : 'Odśwież'}
        </button>
      </div>
      {error && <div className="text-xs text-red-600">{error}</div>}
      {opps.length === 0 && !loading && <div className="text-xs text-slate-500">Brak okazji arbitrażowych &lt;0.25%.</div>}
      <ul className="space-y-2">
        {opps.map((o, idx) => (
          <li key={idx} className="border border-emerald-200 rounded-lg p-3">
            <div className="font-semibold text-emerald-700">{o.symbol}</div>
            <div>Kup na <b>{o.buy_exchange}</b> @ {o.buy_price.toFixed(2)}</div>
            <div>Sprzedaj na <b>{o.sell_exchange}</b> @ {o.sell_price.toFixed(2)}</div>
            <div className="text-sm text-emerald-600">Spread: {o.spread_pct.toFixed(2)}%</div>
            <div className="text-xs text-slate-500">{new Date(o.timestamp_ms).toLocaleTimeString('pl-PL', { hour12: false })}</div>
          </li>
        ))}
      </ul>
      <p className="text-xs text-slate-500">
        Alerty generuje moduł arbitrage — rozważ automatyczny execution jeśli spread jest stabilny.
      </p>
    </div>
  );
};
