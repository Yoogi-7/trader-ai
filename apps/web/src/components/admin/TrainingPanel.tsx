import { useState } from 'react';
import useSWR from 'swr';
import { api, fetcher } from '../../api';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

export const TrainingPanel: React.FC = () => {
  const { data, mutate } = useSWR('/train/status?limit=50&offset=0', fetcher, { refreshInterval: 4000 });
  const [form, setForm] = useState<any>({
    symbol: 'BTC/USDT', tf: '15m', n_folds: 5, capital: 1000, risk: 'MED',
    start_ts: 0, end_ts: Date.now()
  });

  async function run() {
    await api.trainRun(form);
    mutate();
  }

  const points = (data?.items ?? []).filter((r:any)=>r.metrics_json?.ok).map((r:any)=>({
    run: r.id,
    hr1: r.metrics_json.metrics_avg?.hit_rate_tp1 ?? 0,
    pf: r.metrics_json.metrics_avg?.pf ?? 0,
    mar: r.metrics_json.metrics_avg?.mar ?? 0,
  }));

  return (
    <div className="bg-white rounded-2xl shadow p-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Training (Walk-Forward + Tuning)</h2>
        <button onClick={run} className="px-3 py-2 rounded bg-indigo-600 text-white">Run</button>
      </div>
      <div className="grid md:grid-cols-5 gap-2 mt-3">
        {Object.entries(form).map(([k,v])=>(
          <label key={k} className="text-sm">
            <span className="block text-slate-600">{k}</span>
            <input className="w-full border rounded px-2 py-1" value={v as any} onChange={e=>setForm({...form, [k]: Number.isFinite(+e.target.value)? Number(e.target.value) : e.target.value})}/>
          </label>
        ))}
      </div>

      <div className="h-56 mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="run" />
            <YAxis yAxisId="left" />
            <YAxis yAxisId="right" orientation="right" />
            <Tooltip />
            <Line yAxisId="left" type="monotone" dataKey="hr1" dot={false} />
            <Line yAxisId="right" type="monotone" dataKey="pf" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="overflow-auto mt-4">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-100"><tr><th className="p-2 text-left">ID</th><th className="p-2 text-left">Status</th><th className="p-2 text-left">HR1</th><th className="p-2 text-left">PF</th><th className="p-2 text-left">MAR</th></tr></thead>
          <tbody>
            {(data?.items ?? []).map((r:any)=>(
              <tr key={r.id} className="border-b">
                <td className="p-2">{r.id}</td>
                <td className="p-2">{r.status}</td>
                <td className="p-2">{(r.metrics_json?.metrics_avg?.hit_rate_tp1 ?? 0).toFixed(2)}</td>
                <td className="p-2">{(r.metrics_json?.metrics_avg?.pf ?? 0).toFixed(2)}</td>
                <td className="p-2">{(r.metrics_json?.metrics_avg?.mar ?? 0).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
