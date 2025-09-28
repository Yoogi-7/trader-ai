import Head from 'next/head';
import { useEffect } from 'react';
import { useRouter } from 'next/router';
import { BackfillPanel } from '../src/components/admin/BackfillPanel';
import { SystemStatusPanel } from '../src/components/admin/SystemStatusPanel';
import { TrainingPanel } from '../src/components/admin/TrainingPanel';
import { BacktestPanel } from '../src/components/admin/BacktestPanel';
import { RegistryPanel } from '../src/components/admin/RegistryPanel';
import { DriftPanel } from '../src/components/admin/DriftPanel';
import { UserManagementPanel } from '../src/components/admin/UserManagementPanel';
import { useAuth } from '../src/context/AuthContext';

export default function Admin() {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading) {
      if (!user) {
        router.replace('/login');
      } else if (user.role !== 'ADMIN') {
        router.replace('/');
      }
    }
  }, [user, loading, router]);

  if (loading || !user || user.role !== 'ADMIN') {
    return (
      <main className="min-h-screen flex items-center justify-center bg-slate-50">
        <p className="text-slate-600">Ładowanie…</p>
      </main>
    );
  }

  return (
    <>
      <Head>
        <title>Trader AI — Admin</title>
      </Head>
      <main className="min-h-screen bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
          <h1 className="text-2xl font-bold">Trader AI — Panel administratora</h1>

          <SystemStatusPanel />
          <BackfillPanel />
          <TrainingPanel />
          <BacktestPanel />
          <RegistryPanel />
          <DriftPanel />
          <UserManagementPanel />
        </div>
      </main>
    </>
  );
}
