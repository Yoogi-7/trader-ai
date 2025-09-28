import { useState } from 'react';
import useSWR from 'swr';
import { api, fetcher } from '../../api';

const roles: Array<'ADMIN' | 'USER'> = ['ADMIN', 'USER'];

export const UserManagementPanel: React.FC = () => {
  const { data, mutate, isLoading } = useSWR('/users', fetcher, { refreshInterval: 10000 });
  const [form, setForm] = useState({ email: '', password: '', role: 'USER' as 'ADMIN' | 'USER' });
  const [error, setError] = useState<string | null>(null);

  async function createUser() {
    setError(null);
    try {
      await api.createUser(form);
      setForm({ email: '', password: '', role: 'USER' });
      mutate();
    } catch (err: any) {
      setError(err.message || 'Nie udało się utworzyć użytkownika');
    }
  }

  async function resetPassword(id: number) {
    const pwd = prompt('Nowe hasło:');
    if (!pwd) return;
    await api.updateUser(id, { password: pwd });
    mutate();
  }

  async function changeRole(id: number, role: 'ADMIN' | 'USER') {
    await api.updateUser(id, { role });
    mutate();
  }

  const users = data ?? [];

  return (
    <div className="bg-white rounded-2xl shadow p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Użytkownicy</h2>
      </div>

      <div className="grid md:grid-cols-3 gap-2">
        <label className="text-sm">
          <span className="block text-slate-600">Email</span>
          <input className="w-full border rounded px-2 py-1" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </label>
        <label className="text-sm">
          <span className="block text-slate-600">Hasło</span>
          <input className="w-full border rounded px-2 py-1" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </label>
        <label className="text-sm">
          <span className="block text-slate-600">Rola</span>
          <select className="w-full border rounded px-2 py-1" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as 'ADMIN' | 'USER' })}>
            {roles.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
        </label>
      </div>
      {error && <div className="text-sm text-red-600">{error}</div>}
      <button onClick={createUser} className="px-3 py-2 bg-indigo-600 text-white rounded">
        Dodaj użytkownika
      </button>

      <div className="overflow-auto">
        {isLoading && <div className="text-sm text-slate-500">Ładowanie…</div>}
        <table className="min-w-full text-sm">
          <thead className="bg-slate-100">
            <tr>
              <th className="text-left p-2">ID</th>
              <th className="text-left p-2">Email</th>
              <th className="text-left p-2">Rola</th>
              <th className="text-left p-2">Ryzyko</th>
              <th className="text-left p-2">Kapitał</th>
              <th className="text-left p-2">Akcje</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u: any) => (
              <tr key={u.id} className="border-b">
                <td className="p-2">{u.id}</td>
                <td className="p-2">{u.email}</td>
                <td className="p-2">
                  <select value={u.role} onChange={(e) => changeRole(u.id, e.target.value as 'ADMIN' | 'USER')} className="border rounded px-2 py-1">
                    {roles.map((role) => (
                      <option key={role} value={role}>
                        {role}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="p-2">{u.risk_profile}</td>
                <td className="p-2">{u.capital}</td>
                <td className="p-2 space-x-2">
                  <button onClick={() => resetPassword(u.id)} className="text-indigo-600 text-sm">
                    Reset hasła
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
