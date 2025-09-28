import { useMemo } from 'react';
import useSWR from 'swr';
import { fetcher } from '../../api';

function parseDate(value: unknown): Date | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'number') {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  if (typeof value === 'string') {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  return null;
}

function formatDate(value: unknown): string {
  const date = parseDate(value);
  if (!date) return '-';
  return `${date.toLocaleString()} (${formatRelative(date)})`;
}

function formatRelative(date: Date): string {
  const now = Date.now();
  const diff = Math.round((now - date.getTime()) / 1000);
  if (!Number.isFinite(diff)) return '';
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

interface SummaryData {
  backfill: Array<{ symbol: string; tf: string; status: string; updated_at?: string; last_ts_completed?: number | string | null; }>;
  training: Array<{ id: number; status: string; params?: any; started_at?: string; finished_at?: string; metrics?: any; }>;
  signals: Array<{ id: string; symbol: string; tf: string; dir: string; ts: number | string; status: string; expected_net_pct?: number; confidence?: number; }>;
  resample: Record<string, { rows: number; last_ts: string | null }>;
  features: Array<{ symbol: string; tf: string; version: string; rows: number; last_ts: string | null }>;
}

export const SystemStatusPanel: React.FC = () => {
  const { data, isLoading, error } = useSWR<SummaryData>('/admin/summary', fetcher, { refreshInterval: 5000 });

  const timeline = useMemo(() => {
    if (!data) return [] as Array<{ label: string; ts: Date | null; description: string }>;
    const items: Array<{ label: string; ts: Date | null; description: string }> = [];

    data.backfill?.forEach((row) => {
      items.push({
        label: 'Backfill',
        ts: parseDate(row.updated_at),
        description: `${row.symbol} ${row.tf} → ${row.status}${row.last_ts_completed ? ` up to ${formatDate(row.last_ts_completed)}` : ''}`,
      });
    });

    data.training?.forEach((row) => {
      items.push({
        label: 'Training',
        ts: parseDate(row.started_at),
        description: `Run ${row.id} (${row.params?.symbol ?? 'n/a'}) → ${row.status}`,
      });
    });

    data.signals?.forEach((row) => {
      items.push({
        label: 'Signal',
        ts: parseDate(row.ts),
        description: `${row.symbol} ${row.dir} (${row.status})`,
      });
    });

    return items
      .filter((item) => item.ts !== null)
      .sort((a, b) => (b.ts!.getTime() - a.ts!.getTime()))
      .slice(0, 15);
  }, [data]);

  return (
    <div className="bg-white rounded-2xl shadow p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Status systemu</h2>
        <span className="text-sm text-slate-500">odświeżanie co 5s</span>
      </div>

      {error && <div className="text-sm text-red-600">{String(error)}</div>}
      {isLoading && <div className="text-sm text-slate-500">Ładowanie…</div>}

      {timeline.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-slate-600">Ostatnie operacje</h3>
          <ul className="mt-2 space-y-1 text-sm">
            {timeline.map((item, idx) => (
              <li key={idx} className="flex justify-between border-b border-slate-100 py-1">
                <span className="font-medium text-slate-700">{item.label}</span>
                <span className="text-slate-600 flex-1 px-2">{item.description}</span>
                <span className="text-slate-500">{item.ts ? formatRelative(item.ts) : '-'} </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        <section>
          <h3 className="text-sm font-semibold text-slate-600">Resample</h3>
          <table className="w-full text-sm mt-2">
            <thead className="bg-slate-100">
              <tr>
                <th className="text-left p-2">Widok</th>
                <th className="text-left p-2">Wiersze</th>
                <th className="text-left p-2">Ostatnia świeca</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data?.resample ?? {}).map(([view, info]) => (
                <tr key={view} className="border-b">
                  <td className="p-2">{view}</td>
                  <td className="p-2">{info.rows}</td>
                  <td className="p-2">{formatDate(info.last_ts)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section>
          <h3 className="text-sm font-semibold text-slate-600">Features</h3>
          <table className="w-full text-sm mt-2">
            <thead className="bg-slate-100">
              <tr>
                <th className="text-left p-2">Symbol</th>
                <th className="text-left p-2">TF</th>
                <th className="text-left p-2">Wersja</th>
                <th className="text-left p-2">Ostatnia świeca</th>
              </tr>
            </thead>
            <tbody>
              {(data?.features ?? []).map((row, idx) => (
                <tr key={`${row.symbol}-${row.tf}-${row.version}-${idx}`} className="border-b">
                  <td className="p-2">{row.symbol}</td>
                  <td className="p-2">{row.tf}</td>
                  <td className="p-2">{row.version}</td>
                  <td className="p-2">{formatDate(row.last_ts)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
};
