import { useState } from 'react';
import { api } from '../api';

export const RiskForm: React.FC<{
  userId: number;
  onUserChange: (n:number)=>void;
  onSaved: ()=>void;
}> = ({ userId, onUserChange, onSaved }) => {
  const [risk_profile, setRisk] = useState<'LOW'|'MED'|'HIGH'>('LOW');
  const [capital, setCapital] = useState<number>(100);
  const [pairs, setPairs] = useState<string>('BTC/USDT,ETH/USDT');

  async function save() {
    await api.setProfile({ user_id: userId, risk_profile, capital, prefs: { pairs: pairs.split(',').map(s=>s.trim()) } });
    onSaved();
  }

  return (
    <div className="space-y-2">
      <label className="text-sm">
        <span className="block text-slate-600">User ID</span>
        <input className="w-full border rounded px-2 py-1" value={userId} onChange={e=>onUserChange(Number(e.target.value))}/>
      </label>
      <label className="text-sm">
        <span className="block text-slate-600">Risk</span>
        <select className="w-full border rounded px-2 py-1" value={risk_profile} onChange={e=>setRisk(e.target.value as any)}>
          <option value="LOW">LOW</option><option value="MED">MED</option><option value="HIGH">HIGH</option>
        </select>
      </label>
      <label className="text-sm">
        <span className="block text-slate-600">Capital ($)</span>
        <input className="w-full border rounded px-2 py-1" value={capital} onChange={e=>setCapital(Number(e.target.value))}/>
      </label>
      <label className="text-sm">
        <span className="block text-slate-600">Pairs</span>
        <input className="w-full border rounded px-2 py-1" value={pairs} onChange={e=>setPairs(e.target.value)}/>
      </label>
      <button onClick={save} className="px-3 py-2 rounded-lg bg-indigo-600 text-white">Zapisz profil</button>
    </div>
  );
};
