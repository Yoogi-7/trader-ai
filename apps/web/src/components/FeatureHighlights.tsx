'use client';

import { useAuth } from '../context/AuthContext';

export const FeatureHighlights: React.FC = () => {
  const { user } = useAuth();
  const maxAllocation = (() => {
    const parsed = user?.prefs?.max_allocation_pct;
    if (typeof parsed === 'number' && Number.isFinite(parsed)) {
      return `${Math.round(parsed * 1000) / 10}%`;
    }
    return 'domyślne 10%';
  })();

  const minConfidence = (() => {
    const parsed = user?.prefs?.min_confidence_rating;
    if (typeof parsed === 'number' && Number.isFinite(parsed)) {
      return `${parsed}%`;
    }
    return 'brak (100% sygnałów)';
  })();

  return (
    <div className="grid md:grid-cols-3 gap-3 text-sm">
      <div className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-4 space-y-2">
        <h3 className="text-sm font-semibold text-indigo-700">Dynamic Position Sizing</h3>
        <p className="text-slate-600">
          Kapitał w trade dobierany automatycznie na podstawie zmienności, z limitem ustawionym przez Ciebie ({maxAllocation}).
        </p>
        <p className="text-xs text-slate-500">Regime + sentiment wpływają na scaling pozycji.</p>
      </div>
      <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4 space-y-2">
        <h3 className="text-sm font-semibold text-emerald-700">Multi-TP &amp; Trailing</h3>
        <p className="text-slate-600">
          Każdy trade targetuje TP1/TP2/TP3 z automatycznym trail stopem po pierwszym take profit – w historii zobaczysz, które poziomy zostały trafione.
        </p>
        <p className="text-xs text-slate-500">Journal wizualizuje wpływ częściowych realizacji na equity.</p>
      </div>
      <div className="rounded-xl border border-amber-200 bg-amber-50/40 p-4 space-y-2">
        <h3 className="text-sm font-semibold text-amber-700">AI Signal Confidence</h3>
        <p className="text-slate-600">
          Każdy sygnał ma rating 1–100. Aktualny filtr: {minConfidence}. Jeśli oceniasz ręcznie – patrz kolumny „Rating” i „Sentiment”.
        </p>
        <p className="text-xs text-slate-500">Wysokie confidence potwierdzają też dobre wyniki w dzienniku.</p>
      </div>
      <div className="rounded-xl border border-rose-200 bg-rose-50/40 p-4 space-y-2">
        <h3 className="text-sm font-semibold text-rose-700">Sentiment-to-Trade Bridge</h3>
        <p className="text-slate-600">
          Bot wzmacnia LONGi gdy social sentiment ≥ 80/100 i redukuje pozycję przy negatywnym tonie. W dzienniku znajdziesz agregaty sentymentu.
        </p>
        <p className="text-xs text-slate-500">W kartach „Do poprawy” zobaczysz kontekst sentymentu przy stratach.</p>
      </div>
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2">
        <h3 className="text-sm font-semibold text-slate-700">Market Regime Detector</h3>
        <p className="text-slate-600">
          Regime (trend, boczniak, wysoka zmienność) steruje TP, sizingiem i wpisuje się w dziennik – sprawdź tabelę „Regime stats”.
        </p>
        <p className="text-xs text-slate-500">Każdy sygnał w historii ma oznaczenie bieżącego regime.</p>
      </div>
      <div className="rounded-xl border border-blue-200 bg-blue-50/40 p-4 space-y-2">
        <h3 className="text-sm font-semibold text-blue-700">AI Trading Journal</h3>
        <p className="text-slate-600">
          Equity curve, błędy i najlepsze zagrania aktualizują się automatycznie – idealne do śledzenia progresu i feedbacku dla modeli.
        </p>
        <p className="text-xs text-slate-500">Znajdziesz go obok risk dashboardu.</p>
      </div>
    </div>
  );
};
