import { useState } from 'react';
import useSWR from 'swr';
import { api, fetcher } from '../../api';

function formatDate(value: unknown): string {
  if (value === null || value === undefined) return '-';
  const date = typeof value === 'number' ? new Date(value) : new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  const diff = (Date.now() - date.getTime()) / 1000;
  let rel: string;
  if (diff < 60) rel = `${Math.floor(diff)}s ago`;
  else if (diff < 3600) rel = `${Math.floor(diff / 60)}m ago`;
  else if (diff < 86400) rel = `${Math.floor(diff / 3600)}h ago`;
  else rel = `${Math.floor(diff / 86400)}d ago`;
  return `${date.toLocaleString()} (${rel})`;
}

export const BackfillPanel: React.FC = () => {
  const [symbols, setSymbols] = useState('BTC/USDT,ETH/USDT');
  const [tf, setTf] = useState('15m');
  const { data, mutate, isLoading } = useSWR('/backfill/status?limit=200&offset=0', fetcher, { refreshInterval: 3000 });

  async function start() {
    await api.backfillStart(symbols.split(',').map((s) => s.trim()).filter(Boolean), tf, null, null);
    mutate();
  }

  const rows = data?.items ?? [];

  return (
    <div className="bg-white rounded-2xl shadow p-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Backfill</h2>
        <button onClick={start} className="px-3 py-2 rounded bg-indigo-600 text-white">Start</button>
      </div>
      <div className="grid md:grid-cols-3 gap-2 mt-3">
        <label className="text-sm">Symbols
          <input className="w-full border rounded px-2 py-1" value={symbols} onChange={(e) => setSymbols(e.target.value)} />
        </label>
        <label className="text-sm">TF
          <select className="w-full border rounded px-2 py-1" value={tf} onChange={(e) => setTf(e.target.value)}>
            {['1m', '5m', '15m', '1h', '4h', '1d'].map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="overflow-auto mt-4 max-h-80">
        {isLoading && <div className="text-sm text-slate-500">Ładowanie…</div>}
        <table className="min-w-full text-sm">
          <thead className="bg-slate-100">
            <tr>
              <th className="text-left p-2">Symbol</th>
              <th className="text-left p-2">TF</th>
              <th className="text-left p-2">Status</th>
              <th className="text-left p-2">Postęp</th>
              <th className="text-left p-2">Ostatnia świeca</th>
              <th className="text-left p-2">Aktualizacja</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r: any) => (
              <tr key={`${r.symbol}-${r.tf}`} className="border-b">
                <td className="p-2">{r.symbol}</td>
                <td className="p-2">{r.tf}</td>
                <td className="p-2">{r.status}</td>
                <td className="p-2">
                  {r.progress_pct !== undefined && r.progress_pct !== null
                    ? `${r.progress_pct}% (${r.done ?? 0}/${r.total ?? '-'})`
                    : '-'}
                </td>
                <td className="p-2">{formatDate(r.last_ts_completed)}</td>
                <td className="p-2 text-slate-500">{formatDate(r.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
