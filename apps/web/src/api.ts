export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetcher(path: string) {
  const res = await fetch(`${API_URL}${path.startsWith('/') ? path : `/${path}`}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function poster<T=any>(path: string, body: any): Promise<T> {
  const res = await fetch(`${API_URL}${path.startsWith('/') ? path : `/${path}`}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let txt = await res.text();
    try { const j = JSON.parse(txt); throw new Error(j.detail?.reason || txt); } catch { throw new Error(txt); }
  }
  return res.json();
}

export const api = {
  backfillStart: (symbols: string[], tf: string, from_ts?: number|null, to_ts?: number|null) =>
    poster('/backfill/start', { symbols, tf, from_ts: from_ts ?? null, to_ts: to_ts ?? null }),
  backfillStatus: () => fetcher('/backfill/status?limit=100&offset=0'),

  trainRun: (params: any) => poster('/train/run', { params }),
  trainStatus: () => fetcher('/train/status?limit=100&offset=0'),

  backtestRun: (params: any) => poster('/backtest/run', { params }),
  backtestResults: () => fetcher('/backtest/results?limit=50&offset=0'),

  signalsHistory: (q='') => fetcher(`/signals/history?${q}`),

  signalAuto: (payload: any) => poster('/signals/auto', payload),

  setProfile: (body: {user_id:number, risk_profile:'LOW'|'MED'|'HIGH', capital:number, prefs:any}) =>
    poster('/settings/profile', body),
};
