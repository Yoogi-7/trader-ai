import Head from 'next/head';
import useSWR from 'swr';
import { useEffect } from 'react';
import { useRouter } from 'next/router';
import { fetcher } from '../src/api';
import { useAuth } from '../src/context/AuthContext';
import { SignalsLive } from '../src/components/SignalsLive';
import { HistoryTable } from '../src/components/HistoryTable';
import { Simulator } from '../src/components/Simulator';
import { RiskForm } from '../src/components/RiskForm';
import { Leaderboard } from '../src/components/Leaderboard';
import { RiskDashboard } from '../src/components/RiskDashboard';
import { TradingJournal } from '../src/components/TradingJournal';

export default function Home() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const { data: history } = useSWR(() => (user ? '/signals/history?limit=100&offset=0' : null), fetcher, {
    refreshInterval: 5000,
  });

  const viewParam = Array.isArray(router.query.view) ? router.query.view[0] : router.query.view;
  const adminViewingUser = user?.role === 'ADMIN' && viewParam === 'user';

  useEffect(() => {
    if (!loading) {
      if (!user) {
        router.replace('/login');
      } else if (user.role === 'ADMIN' && !adminViewingUser) {
        router.replace('/admin');
      }
    }
  }, [user, loading, router, adminViewingUser]);

  if (loading || !user || (user.role !== 'USER' && !adminViewingUser)) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-slate-50">
        <p className="text-slate-600">Ładowanie…</p>
      </main>
    );
  }

  return (
    <>
      <Head>
        <title>Trader AI — Panel użytkownika</title>
      </Head>
      <main className="min-h-screen bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
            <h1 className="text-2xl font-bold">Trader AI — Panel użytkownika</h1>
            {adminViewingUser && (
              <button
                onClick={() => router.push('/admin')}
                className="self-start md:self-auto px-3 py-2 rounded bg-slate-200 text-slate-700 hover:bg-slate-300"
              >
                Wróć do panelu administratora
              </button>
            )}
          </div>

          <div className="mb-6">
            <Leaderboard />
          </div>

          <section className="grid md:grid-cols-3 gap-4">
            <div className="col-span-2">
              <div className="bg-white rounded-2xl shadow p-4 mb-4">
                <h2 className="font-semibold mb-2">Live sygnały</h2>
                <SignalsLive />
              </div>

              <div className="bg-white rounded-2xl shadow p-4">
                <h2 className="font-semibold mb-2">Historia sygnałów</h2>
                <HistoryTable rows={history?.signals ?? []} />
              </div>
            </div>

            <div className="col-span-1 space-y-4">
              <div className="bg-white rounded-2xl shadow p-4">
                <h2 className="font-semibold mb-3">Trading journal</h2>
                <TradingJournal />
              </div>
              <div className="bg-white rounded-2xl shadow p-4">
                <h2 className="font-semibold mb-3">Risk dashboard</h2>
                <RiskDashboard />
              </div>
              <div className="bg-white rounded-2xl shadow p-4">
                <h2 className="font-semibold mb-3">Ustawienia profilu</h2>
                <RiskForm onSaved={() => {}} />
              </div>

              <div className="bg-white rounded-2xl shadow p-4">
                <h2 className="font-semibold mb-3">Symulator (what-if)</h2>
                <Simulator />
              </div>
            </div>
          </section>
        </div>
      </main>
    </>
  );
}
