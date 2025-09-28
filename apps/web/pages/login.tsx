import { FormEvent, useState, useEffect } from 'react';
import Head from 'next/head';
import { useAuth } from '../src/context/AuthContext';

export default function Login() {
  const { login, user, loading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && user) {
      // redirect handled in AuthProvider login
      window.location.href = user.role === 'ADMIN' ? '/admin' : '/';
    }
  }, [user, loading]);

  async function handleSubmit(evt: FormEvent) {
    evt.preventDefault();
    setError(null);
    try {
      await login(email, password);
    } catch (err: any) {
      setError(err.message || 'Logowanie nie powiodło się');
    }
  }

  return (
    <>
      <Head>
        <title>Trader AI — Logowanie</title>
      </Head>
      <main className="min-h-screen flex items-center justify-center bg-slate-100">
        <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md space-y-4">
          <h1 className="text-2xl font-bold text-center">Logowanie</h1>
          <label className="block text-sm">
            <span className="text-slate-600">Email</span>
            <input type="email" className="w-full border rounded px-3 py-2" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="block text-sm">
            <span className="text-slate-600">Hasło</span>
            <input type="password" className="w-full border rounded px-3 py-2" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          {error && <div className="text-sm text-red-600">{error}</div>}
          <button type="submit" className="w-full py-2 rounded bg-indigo-600 text-white font-semibold">Zaloguj się</button>
        </form>
      </main>
    </>
  );
}
