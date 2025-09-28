export const API_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const RAW_PREFIX = process.env.NEXT_PUBLIC_API_PREFIX ?? '/api';
const API_PREFIX = RAW_PREFIX ? (RAW_PREFIX.startsWith('/') ? RAW_PREFIX : `/${RAW_PREFIX}`) : '';

function buildUrl(path: string) {
  const suffix = path.startsWith('/') ? path : `/${path}`;
  const raw = `${API_URL}${API_PREFIX}${suffix}`;
  return raw.replace(/([^:]\/)\/+/g, '$1').replace('http:/', 'http://').replace('https:/', 'https://');
}

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem('auth_token');
}

function buildHeaders(extra?: Record<string, string>): HeadersInit {
  const headers: Record<string, string> = { Accept: 'application/json', ...(extra ?? {}) };
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

function handleUnauthorized(status: number) {
  if (status === 401 && typeof window !== 'undefined') {
    window.localStorage.removeItem('auth_token');
    if (!window.location.pathname.startsWith('/login')) {
      window.location.href = '/login';
    }
  }
}

export async function fetcher(path: string) {
  const res = await fetch(buildUrl(path), { headers: buildHeaders() });
  if (!res.ok) {
    handleUnauthorized(res.status);
    throw new Error(await res.text());
  }
  return res.json();
}

export async function poster<T = any>(path: string, body: any): Promise<T> {
  const res = await fetch(buildUrl(path), {
    method: 'POST',
    headers: buildHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    handleUnauthorized(res.status);
    const txt = await res.text();
    try {
      const json = JSON.parse(txt);
      throw new Error(json.detail?.reason || json.detail || txt);
    } catch {
      throw new Error(txt);
    }
  }
  return res.json();
}

export const api = {
  backfillStart: (symbols: string[], tf: string, from_ts?: number | null, to_ts?: number | null) =>
    poster('/backfill/start', { symbols, tf, from_ts: from_ts ?? null, to_ts: to_ts ?? null }),
  backfillStatus: () => fetcher('/backfill/status?limit=100&offset=0'),

  trainRun: (params: any) => poster('/train/run', { params }),
  trainStatus: () => fetcher('/train/status?limit=100&offset=0'),

  backtestRun: (params: any) => poster('/backtest/run', { params }),
  backtestResults: () => fetcher('/backtest/results?limit=50&offset=0'),

  signalsHistory: (q = '') => fetcher(`/signals/history?${q}`),
  signalsLive: () => fetcher('/signals/live'),
  signalAuto: (payload: any) => poster('/signals/auto', payload),

  setProfile: (body: { user_id?: number | null; risk_profile: 'LOW' | 'MED' | 'HIGH'; capital: number; prefs: any }) =>
    poster('/settings/profile', body),
  setCapital: (amount: number) => poster('/capital', { amount }),

  login: (payload: { email: string; password: string }) => poster('/auth/login', payload),
  me: () => fetcher('/auth/me'),
  users: () => fetcher('/users'),
  createUser: (payload: { email: string; password: string; role: 'ADMIN' | 'USER'; risk_profile?: string; capital?: number; prefs?: any }) =>
    poster('/users', payload),
  updateUser: (userId: number, payload: any) => poster(`/users/${userId}`, payload),
  leaderboard: () => fetcher('/leaderboard'),
  riskDashboard: () => fetcher('/risk/dashboard'),
};

export { getToken };
