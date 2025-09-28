'use client';

import useSWR from 'swr';
import { useMemo } from 'react';
import { fetcher } from '../api';
import { useAuth } from '../context/AuthContext';

interface LiveSignal {
  id: string;
  symbol: string;
  dir: 'LONG' | 'SHORT';
  risk: string;
  confidence_rating?: number | null;
  market_regime?: string | null;
  sentiment_rating?: number | null;
  tp?: number[] | null;
  sl: number;
}

interface LiveResponse {
  signals: LiveSignal[];
}

const DEFAULT_SPLIT = '30% / 40% / 30%';
const TRAIL_OFFSET = '0.2%';

export const StrategyAssistant: React.FC = () => {
  const { user } = useAuth();
  const { data } = useSWR<LiveResponse>('/signals/live', fetcher, { refreshInterval: 15_000 });
  const latest = data?.signals?.[0];

  const maxAllocation = useMemo(() => {
    const raw = user?.prefs?.max_allocation_pct;
    if (typeof raw === 'number' && Number.isFinite(raw)) {
      return `${Math.round(raw * 1000) / 10}% portfela`;
    }
    return 'domyślne 10% portfela';
  }, [user]);

  const minConfidence = useMemo(() => {
    const raw = user?.prefs?.min_confidence_rating;
    if (typeof raw === 'number' && Number.isFinite(raw)) {
      return `${raw}/100`;
    }
    return 'brak filtra (100/100)';
  }, [user]);

  const currentRiskFraction = useMemo(() => {
    if (!latest) return null;
    const parsed = parseFloat(String(latest.risk));
    if (!Number.isFinite(parsed)) return null;
    return `${(parsed * 100).toFixed(2)}%`; 
  }, [latest]);

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Strategia AI — co dzieje się pod maską?</h2>
        {latest && (
          <span className="text-xs text-slate-500">
            Ostatni sygnał: {latest.symbol} ({latest.dir})
          </span>
        )}
      </div>
      <div className="grid md:grid-cols-3 gap-3 text-sm">
        <div className="rounded-xl bg-indigo-50/60 border border-indigo-100 p-3 space-y-1">
          <div className="font-semibold text-indigo-700">Dynamic position sizing</div>
          <div className="text-slate-600">
            Limit wykorzystania: <b>{maxAllocation}</b>. Bieżące ryzyko dla ostatniego sygnału: <b>{currentRiskFraction ?? 'n/a'}</b>.
          </div>
          <div className="text-xs text-slate-500">Sygnał skaluje się wg zmienności, regime i sentymentu.</div>
        </div>
        <div className="rounded-xl bg-emerald-50/70 border border-emerald-100 p-3 space-y-1">
          <div className="font-semibold text-emerald-700">Multi-TP &amp; trailing stop</div>
          <div className="text-slate-600">
            Podział TP: <b>{DEFAULT_SPLIT}</b>. Trailing aktywny po TP1 z offsetem <b>{TRAIL_OFFSET}</b>.
          </div>
          {latest?.tp && (
            <div className="text-xs text-slate-500">Aktualne cele: {latest.tp.map((v) => v.toFixed(2)).join(' / ')}</div>
          )}
        </div>
        <div className="rounded-xl bg-amber-50/60 border border-amber-100 p-3 space-y-1">
          <div className="font-semibold text-amber-700">Confidence &amp; sentiment</div>
          <div className="text-slate-600">
            Filtr confidence: <b>{minConfidence}</b>. Ostatni rating: <b>{latest?.confidence_rating ?? 'n/a'}</b>.
          </div>
          <div className="text-xs text-slate-500">Sentiment wspiera trade: {typeof latest?.sentiment_rating === 'number' ? `${latest?.sentiment_rating}/100` : 'n/a'}.</div>
        </div>
      </div>
      <div className="grid md:grid-cols-3 gap-3 text-sm">
        <div className="rounded-xl bg-rose-50/60 border border-rose-100 p-3 space-y-1">
          <div className="font-semibold text-rose-700">Market regime detector</div>
          <div className="text-slate-600">
            Aktualny regime: <b>{latest?.market_regime ?? 'brak sygnałów'}</b>. Journal agreguje skuteczność dla każdego otoczenia rynku.
          </div>
          <div className="text-xs text-slate-500">Regime wpływa na TP i wielkość pozycji.</div>
        </div>
        <div className="rounded-xl bg-blue-50/60 border border-blue-100 p-3 space-y-1">
          <div className="font-semibold text-blue-700">AI trading journal</div>
          <div className="text-slate-600">
            Śledź equity curve, błędy i najlepsze zagrania w karcie „Trading journal”. Dane odświeżają się co minutę.
          </div>
          <div className="text-xs text-slate-500">Ostatnia aktualizacja odzwierciedla powyższy sygnał.</div>
        </div>
        <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 space-y-1">
          <div className="font-semibold text-slate-700">Cross-exchange arbitrage</div>
          <div className="text-slate-600">
            Panel „Arbitrage radar” pokazuje aktualne różnice cen (BTC/ETH). Podglądaj okazje i reaguj ręcznie albo automatycznie.
          </div>
          <div className="text-xs text-slate-500">Alerty &gt; 0.25% pojawią się na zielono.</div>
        </div>
      </div>
    </div>
  );
};
