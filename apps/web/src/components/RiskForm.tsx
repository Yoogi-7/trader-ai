import { useEffect, useState } from 'react';
import { api } from '../api';
import { useAuth } from '../context/AuthContext';

export const RiskForm: React.FC<{ onSaved: () => void }> = ({ onSaved }) => {
  const { user } = useAuth();
  const [risk_profile, setRisk] = useState<'LOW' | 'MED' | 'HIGH'>('LOW');
  const [capital, setCapital] = useState<number>(100);
  const [pairs, setPairs] = useState<string>('BTC/USDT,ETH/USDT');

  useEffect(() => {
    if (user) {
      setRisk((user.risk_profile as 'LOW' | 'MED' | 'HIGH') ?? 'LOW');
      setCapital(user.capital ?? 100);
    }
  }, [user]);

  async function save() {
    await api.setProfile({ risk_profile, capital, prefs: { pairs: pairs.split(',').map((s) => s.trim()).filter(Boolean) } });
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
        <span className="block text-slate-600">Pary</span>
        <input className="w-full border rounded px-2 py-1" value={pairs} onChange={(e) => setPairs(e.target.value)} />
      </label>
      <button onClick={save} className="px-3 py-2 rounded-lg bg-indigo-600 text-white">
        Zapisz profil
      </button>
    </div>
  );
};
