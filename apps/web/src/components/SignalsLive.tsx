import { useWS } from '../ws';

export const SignalsLive: React.FC = () => {
  const { messages } = useWS();
  const items = messages.filter(m => m?.type === 'signal_published');

  return (
    <div className="overflow-auto max-h-80">
      {items.length === 0 && <div className="text-sm text-slate-500">Brak świeżych eventów.</div>}
      <ul className="space-y-2">
        {items.map((m, idx) => (
          <li key={idx} className="border rounded-xl p-2">
            <div className="text-sm">
              <span className="font-semibold">{m.symbol}</span> — <span>{m.signal_id}</span>
            </div>
            <div className="text-xs text-slate-600">dir: {m.dir}</div>
          </li>
        ))}
      </ul>
    </div>
  );
};
