import useSWR from 'swr';
import { fetcher } from '../../api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

export const DriftPanel: React.FC = () => {
  const { data } = useSWR('/train/status?limit=20&offset=0', fetcher, { refreshInterval: 5000 });

  const points = (data?.items ?? []).map((r:any)=>({
    run: r.id,
    psi: r.metrics_json?.drift?.psi ?? 0,
    ks: r.metrics_json?.drift?.ks ?? 0,
    hr1: r.metrics_json?.metrics_avg?.hit_rate_tp1 ?? 0,
  }));

  return (
    <div className="bg-white rounded-2xl shadow p-4">
      <h2 className="font-semibold mb-3">Monitoring driftu (PSI/KS)</h2>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={points}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="run" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="psi" />
            <Bar dataKey="ks" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="text-xs text-slate-500 mt-2">Wartości pochodzą z `training_runs.metrics_json` (jeśli wypełnione).</div>
    </div>
  );
};
