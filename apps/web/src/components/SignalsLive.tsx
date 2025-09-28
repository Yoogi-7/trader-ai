import { useMemo } from 'react';
import { useAuth } from '../context/AuthContext';
import { useWS } from '../ws';

export const SignalsLive: React.FC = () => {
  const { messages } = useWS();
  const { user } = useAuth();
  const minRating = useMemo(() => {
    const value = user?.prefs?.min_confidence_rating;
    if (typeof value !== 'number' || Number.isNaN(value)) return 0;
    return Math.min(100, Math.max(0, value));
  }, [user]);

  const items = useMemo(() => {
    return messages
      .filter((m) => m?.type === 'signal_published')
      .filter((m) => {
        if (!m?.confidence_rating && m?.confidence_rating !== 0) return true;
        return m.confidence_rating >= minRating;
      });
  }, [messages, minRating]);

  return (
    <div className="overflow-auto max-h-80">
      {items.length === 0 && <div className="text-sm text-slate-500">Brak świeżych eventów.</div>}
      <ul className="space-y-2">
        {items.map((m, idx) => (
          <li key={idx} className="border rounded-xl p-2 space-y-1">
            <div className="text-sm">
              <span className="font-semibold">{m.symbol}</span> — <span>{m.signal_id ?? m.id}</span>
            </div>
            <div className="text-xs text-slate-600">dir: {m.dir}</div>
            {typeof m.confidence_rating === 'number' && (
              <div className="text-xs text-indigo-600">rating: {m.confidence_rating}/100</div>
            )}
            {m.market_regime && (
              <div className="text-xs text-teal-600">regime: {m.market_regime}</div>
            )}
            {typeof m.sentiment_rating === 'number' && (
              <div className="text-xs text-rose-600">sentiment: {m.sentiment_rating}/100</div>
            )}
            {m.ai_summary && <div className="text-xs text-emerald-700">{m.ai_summary}</div>}
          </li>
        ))}
      </ul>
    </div>
  );
};
