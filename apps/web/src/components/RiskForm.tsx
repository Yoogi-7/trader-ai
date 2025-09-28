import { useEffect, useState } from 'react';
import { api } from '../api';
import { useAuth } from '../context/AuthContext';

export const RiskForm: React.FC<{ onSaved: () => void }> = ({ onSaved }) => {
  const { user } = useAuth();
  const [risk_profile, setRisk] = useState<'LOW' | 'MED' | 'HIGH'>('LOW');
  const [capital, setCapital] = useState<number>(100);
  const [pairs, setPairs] = useState<string>('BTC/USDT,ETH/USDT');
  const [maxAllocationPct, setMaxAllocationPct] = useState<number>(10);
  const [minConfidenceRating, setMinConfidenceRating] = useState<number>(0);

  useEffect(() => {
    if (user) {
      setRisk((user.risk_profile as 'LOW' | 'MED' | 'HIGH') ?? 'LOW');
      setCapital(user.capital ?? 100);
      if (user.prefs && Array.isArray(user.prefs.pairs)) {
        setPairs(user.prefs.pairs.join(', '));
      }
      const prefMax = user.prefs?.max_allocation_pct;
      if (typeof prefMax === 'number' && Number.isFinite(prefMax)) {
        setMaxAllocationPct(Math.round(prefMax * 1000) / 10);
      }
      const prefConfidence = user.prefs?.min_confidence_rating;
      if (typeof prefConfidence === 'number' && Number.isFinite(prefConfidence)) {
        setMinConfidenceRating(Math.min(100, Math.max(0, prefConfidence)));
      }
    }
  }, [user]);

  async function save() {
    const parsedPairs = pairs
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    const sanitizedMax = Number.isFinite(maxAllocationPct) ? Math.min(100, Math.max(0, maxAllocationPct)) : undefined;
    const prefs = {
      ...(user?.prefs ?? {}),
      pairs: parsedPairs,
      max_allocation_pct: sanitizedMax !== undefined ? sanitizedMax / 100 : undefined,
      min_confidence_rating: Number.isFinite(minConfidenceRating)
        ? Math.min(100, Math.max(0, minConfidenceRating))
        : undefined,
    };
    await api.setProfile({ risk_profile, capital, prefs });
    onSaved();
  }

  return (
    <div className="space-y-2">
      <label className="text-sm">
        <span className="block text-slate-600">Ryzyko</span>
        <select className="w-full border rounded px-2 py-1" value={risk_profile} onChange={(e) => setRisk(e.target.value as any)}>
          <option value="LOW">LOW</option>
          <option value="MED">MED</option>
          <option value="HIGH">HIGH</option>
        </select>
      </label>
      <label className="text-sm">
        <span className="block text-slate-600">Kapitał ($)</span>
        <input className="w-full border rounded px-2 py-1" type="number" value={capital} onChange={(e) => setCapital(Number(e.target.value))} />
      </label>
      <label className="text-sm">
        <span className="block text-slate-600">Maks. wykorzystanie portfela (%)</span>
        <input
          className="w-full border rounded px-2 py-1"
          type="number"
          min={0}
          max={100}
          step={0.1}
          value={maxAllocationPct}
          onChange={(e) => setMaxAllocationPct(Number(e.target.value))}
        />
      </label>
      <label className="text-sm">
        <span className="block text-slate-600">Minimalny rating sygnału (%)</span>
        <input
          className="w-full border rounded px-2 py-1"
          type="number"
          min={0}
          max={100}
          step={1}
          value={minConfidenceRating}
          onChange={(e) => setMinConfidenceRating(Number(e.target.value))}
        />
      </label>
      <label className="text-sm">
        <span className="block text-slate-600">Pary</span>
        <input className="w-full border rounded px-2 py-1" value={pairs} onChange={(e) => setPairs(e.target.value)} />
      </label>
      <button onClick={save} className="px-3 py-2 rounded-lg bg-indigo-600 text-white">
        Zapisz profil
      </button>
    </div>
  );
};
