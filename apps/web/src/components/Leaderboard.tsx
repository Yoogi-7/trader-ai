import useSWR from 'swr';
import { fetcher } from '../api';

interface LeaderboardOverall {
  win_rate: number;
  total_trades: number;
  wins: number;
  period_start_ms: number;
  period_end_ms: number;
}

interface LeaderboardUserEntry {
  rank: number;
  user_id: number;
  email: string;
  capital: number;
  risk_profile: string;
}

interface LeaderboardResponse {
  overall: LeaderboardOverall;
  users: LeaderboardUserEntry[];
}

function formatDate(ms: number): string {
  const date = new Date(ms);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleDateString();
}

export const Leaderboard: React.FC = () => {
  const { data, error, isLoading } = useSWR<LeaderboardResponse>('/leaderboard', fetcher, {
    refreshInterval: 10000,
  });

  if (error) {
    return <div className="bg-white rounded-2xl shadow p-4 text-sm text-red-600">Nie udało się pobrać rankingu.</div>;
  }

  if (isLoading || !data) {
    return <div className="bg-white rounded-2xl shadow p-4 text-sm text-slate-500">Ładowanie rankingu…</div>;
  }

  const winRatePct = (data.overall.win_rate * 100).toFixed(1);

  return (
    <div className="bg-white rounded-2xl shadow p-4 space-y-4">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Leaderboard skuteczności</h2>
          <p className="text-sm text-slate-600">
            Okres: {formatDate(data.overall.period_start_ms)} – {formatDate(data.overall.period_end_ms)}
          </p>
        </div>
        <div className="bg-slate-100 rounded-xl px-4 py-2 text-center">
          <div className="text-xs uppercase text-slate-500">Win rate AI</div>
          <div className="text-2xl font-bold text-emerald-600">{winRatePct}%</div>
          <div className="text-xs text-slate-600">{data.overall.wins} / {data.overall.total_trades} sygnałów</div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-slate-600">Top użytkownicy</h3>
        <div className="overflow-auto mt-2">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100">
              <tr>
                <th className="text-left p-2">#</th>
                <th className="text-left p-2">Użytkownik</th>
                <th className="text-left p-2">Kapitał</th>
                <th className="text-left p-2">Profil ryzyka</th>
              </tr>
            </thead>
            <tbody>
              {data.users.length === 0 && (
                <tr>
                  <td colSpan={4} className="p-3 text-slate-500 text-center">Brak danych rankingowych.</td>
                </tr>
              )}
              {data.users.map((u) => (
                <tr key={u.user_id} className="border-b">
                  <td className="p-2 font-semibold">{u.rank}</td>
                  <td className="p-2">{u.email}</td>
                  <td className="p-2">${u.capital.toFixed(2)}</td>
                  <td className="p-2">{u.risk_profile}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
