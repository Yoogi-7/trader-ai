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

export default function Home() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const { data: history } = useSWR(() => (user ? '/signals/history?limit=100&offset=0' : null), fetcher, {
    refreshInterval: 5000,
  });

  useEffect(() => {
    if (!loading) {
      if (!user) {
        router.replace('/login');
      } else if (user.role === 'ADMIN') {
        router.replace('/admin');
      }
    }
  }, [user, loading, router]);

  if (loading || !user || user.role !== 'USER') {
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
          <h1 className="text-2xl font-bold mb-4">Trader AI — Panel użytkownika</h1>

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
