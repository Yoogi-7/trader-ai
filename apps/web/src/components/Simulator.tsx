import { useEffect, useState } from 'react';
import { api } from '../api';
import { useAuth } from '../context/AuthContext';

export const Simulator: React.FC = () => {
  const { user } = useAuth();
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
    max_allocation_pct: 0.1,
  } as any);
  const [resp, setResp] = useState<any>(null);
  const [err, setErr] = useState<string>('');

  useEffect(() => {
    if (!user) return;
    setForm((prev: any) => ({
      ...prev,
      capital: user.capital ?? prev.capital,
      risk: user.risk_profile ?? prev.risk,
      max_allocation_pct:
        typeof user.prefs?.max_allocation_pct === 'number'
          ? user.prefs.max_allocation_pct
          : prev.max_allocation_pct,
    }));
  }, [user]);

  async function run() {
    setErr('');
    setResp(null);
    try {
      const payload = { ...form };
      payload.max_allocation_pct = Math.min(1, Math.max(0, payload.max_allocation_pct ?? 0));
      const r = await api.signalAuto(payload);
      setResp(r);
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        {[
          ['symbol', 'BTC/USDT'],
          ['tf_base', '15m'],
          ['direction', 'LONG'],
          ['close', 64000],
          ['atr', 120],
          ['desired_leverage', 5],
          ['risk', 'MED'],
          ['capital', 1000],
          ['confidence', 0.6],
        ].map(([k]) => (
          <label key={k} className="text-sm">
            <span className="block text-slate-600">{k}</span>
            <input
              className="w-full border rounded px-2 py-1"
              value={form[k as keyof typeof form] as any}
              onChange={(e) =>
                setForm({
                  ...form,
                  [k]:
                    k === 'symbol' || k === 'tf_base' || k === 'direction' || k === 'risk'
                      ? e.target.value
                      : Number(e.target.value),
                })
              }
            />
          </label>
        ))}
        <label className="text-sm">
          <span className="block text-slate-600">max_allocation_pct (%)</span>
          <input
            className="w-full border rounded px-2 py-1"
            type="number"
            min={0}
            max={100}
            step={0.1}
            value={Math.round((form.max_allocation_pct ?? 0) * 1000) / 10}
            onChange={(e) =>
              setForm({
                ...form,
                max_allocation_pct: Math.min(100, Math.max(0, Number(e.target.value))) / 100,
              })
            }
          />
        </label>
      </div>
      <button onClick={run} className="px-3 py-2 rounded-lg bg-indigo-600 text-white">
        Publikuj (symulacja ≥2% net)
      </button>
      {err && <div className="text-red-600 text-sm">Odrzucone: {err}</div>}
      {resp && (
        <div className="text-sm bg-emerald-50 border border-emerald-200 rounded p-2">
          <div>
            <b>ID:</b> {resp.id}
          </div>
          <div>
            <b>Entry:</b> {resp.entry} <b>SL:</b> {resp.sl} <b>TP:</b> {(resp.tp || []).join(', ')}
          </div>
          <div>
            <b>Net%:</b> {(resp.expected_net_pct * 100).toFixed(2)}%
          </div>
          {typeof resp.confidence_rating === 'number' && (
            <div>
              <b>Rating:</b> {resp.confidence_rating}/100
            </div>
          )}
          {resp.market_regime && (
            <div>
              <b>Regime:</b> {resp.market_regime}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
