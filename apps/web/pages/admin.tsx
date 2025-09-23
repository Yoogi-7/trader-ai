import Head from 'next/head';
import { BackfillPanel } from '../src/components/admin/BackfillPanel';
import { TrainingPanel } from '../src/components/admin/TrainingPanel';
import { BacktestPanel } from '../src/components/admin/BacktestPanel';
import { RegistryPanel } from '../src/components/admin/RegistryPanel';
import { DriftPanel } from '../src/components/admin/DriftPanel';

export default function Admin() {
  return (
    <>
      <Head>
        <title>Trader AI — Admin</title>
      </Head>
      <main className="min-h-screen bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
          <h1 className="text-2xl font-bold">Trader AI — Panel administratora</h1>

          <BackfillPanel />
          <TrainingPanel />
          <BacktestPanel />
          <RegistryPanel />
          <DriftPanel />
        </div>
      </main>
    </>
  );
}
