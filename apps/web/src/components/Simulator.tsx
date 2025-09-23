import { useState } from 'react';
import { api } from '../api';

export const Simulator: React.FC = () => {
  const [form, setForm] = useState({
    symbol: 'BTC/USDT',
    tf_base: '15m',
    direction: 'LONG',
    close: 64000,
    atr: 120,
    desired_leverage: 5,
    risk: 'MED',
    capital: 1000,
    confidence: 0.6,
  } as any);
  const [resp, setResp] = useState<any>(null);
  const [err, setErr] = useState<string>('');

  async function run() {
    setErr('');
    setResp(null);
    try {
      const r = await api.signalAuto(form);
      setResp(r);
    } catch (e:any) {
      setErr(e.message || String(e));
    }
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        {[
          ['symbol','BTC/USDT'],['tf_base','15m'],['direction','LONG'],['close',64000],['atr',120],
          ['desired_leverage',5],['risk','MED'],['capital',1000],['confidence',0.6],
        ].map(([k,def]) => (
          <label key={k} className="text-sm">
            <span className="block text-slate-600">{k}</span>
            <input className="w-full border rounded px-2 py-1"
              value={form[k as keyof typeof form] as any}
              onChange={e=>setForm({...form, [k]: (k==='symbol'||k==='tf_base'||k==='direction'||k==='risk')? e.target.value : Number(e.target.value)})}/>
          </label>
        ))}
      </div>
      <button onClick={run} className="px-3 py-2 rounded-lg bg-indigo-600 text-white">Publikuj (symulacja ≥2% net)</button>
      {err && <div className="text-red-600 text-sm">Odrzucone: {err}</div>}
      {resp && (
        <div className="text-sm bg-emerald-50 border border-emerald-200 rounded p-2">
          <div><b>ID:</b> {resp.id}</div>
          <div><b>Entry:</b> {resp.entry} <b>SL:</b> {resp.sl} <b>TP:</b> {(resp.tp||[]).join(', ')}</div>
          <div><b>Net%:</b> {(resp.expected_net_pct*100).toFixed(2)}%</div>
        </div>
      )}
    </div>
  );
};
