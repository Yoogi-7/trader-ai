import { useState } from 'react';
import useSWR from 'swr';
import { api, fetcher } from '../../api';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

export const BacktestPanel: React.FC = () => {
  const { data, mutate } = useSWR('/backtest/results?limit=50&offset=0', fetcher, { refreshInterval: 4000 });
  const [form, setForm] = useState<any>({
    symbol: 'BTC/USDT', tf: '15m', capital: 1000, risk: 'MED',
    start_ts: 0, end_ts: Date.now(), funding_rate_hourly: 0.00001, slippage_bps: 10, time_stop_min: 240, taker_only: true
  });

  async function run() {
    await api.backtestRun(form);
    mutate();
  }

  const last = (data?.items ?? []).filter((b:any)=>b.summary_json?.metrics?.equity_curve).slice(-1)[0];
  const eq = (last?.summary_json?.metrics?.equity_curve ?? []).map((v:number, i:number)=>({i, eq:v}));

  return (
    <div className="bg-white rounded-2xl shadow p-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Backtest</h2>
        <button onClick={run} className="px-3 py-2 rounded bg-indigo-600 text-white">Run</button>
      </div>

      <div className="grid md:grid-cols-5 gap-2 mt-3">
        {Object.entries(form).map(([k,v])=>(
          <label key={k} className="text-sm">
            <span className="block text-slate-600">{k}</span>
            <input className="w-full border rounded px-2 py-1" value={v as any} onChange={e=>setForm({...form, [k]: Number.isFinite(+e.target.value)? Number(e.target.value) : (e.target.value === 'true' ? true : e.target.value === 'false' ? false : e.target.value)})}/>
          </label>
        ))}
      </div>

      <div className="h-56 mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={eq}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="i" />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="eq" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="overflow-auto mt-4">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-100"><tr><th className="p-2 text-left">ID</th><th className="p-2 text-left">HR1</th><th className="p-2 text-left">PF</th><th className="p-2 text-left">MAR</th><th className="p-2 text-left">DD%</th></tr></thead>
          <tbody>
            {(data?.items ?? []).map((b:any)=>(
              <tr key={b.id} className="border-b">
                <td className="p-2">{b.id}</td>
                <td className="p-2">{(b.summary_json?.metrics?.hit_rate_tp1 ?? 0).toFixed(2)}</td>
                <td className="p-2">{(b.summary_json?.metrics?.pf ?? 0).toFixed(2)}</td>
                <td className="p-2">{(b.summary_json?.metrics?.mar ?? 0).toFixed(2)}</td>
                <td className="p-2">{((b.summary_json?.metrics?.max_dd_pct ?? 0)*100).toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

    </div>
  );
};
