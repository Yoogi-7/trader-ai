import useSWR from 'swr';
import { fetcher } from '../api';

interface RiskMetricsBlock {
  source: 'backtest' | 'live';
  max_drawdown: number | null;
  max_drawdown_pct: number | null;
  avg_profit_per_trade: number | null;
  win_rate: number | null;
  trades: number;
  pnl_total: number | null;
  capital: number | null;
  last_updated_ms: number | null;
}

interface RiskDashboardResp {
  backtest: RiskMetricsBlock;
  live: RiskMetricsBlock;
}

const currencyFormatter = new Intl.NumberFormat('pl-PL', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 2,
});

const numberFormatter = new Intl.NumberFormat('pl-PL', {
  maximumFractionDigits: 0,
});

const percentFormatter = new Intl.NumberFormat('pl-PL', {
  style: 'percent',
  maximumFractionDigits: 1,
});

function formatCurrency(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return '—';
  }
  return currencyFormatter.format(value);
}

function formatPercent(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return '—';
  }
  return percentFormatter.format(value);
}

function formatCount(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return '—';
  }
  return numberFormatter.format(value);
}

function formatTimestamp(value: number | null): string {
  if (!value) {
    return '—';
  }
  try {
    return new Date(value).toLocaleString('pl-PL', {
      hour12: false,
    });
  } catch (err) {
    return '—';
  }
}

interface CardProps {
  title: string;
  metrics: RiskMetricsBlock;
}

function MetricsCard({ title, metrics }: CardProps) {
  return (
    <div className="rounded-xl border border-slate-200 p-3">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-700">{title}</h3>
        <span className="text-xs text-slate-400">Ostatnia aktualizacja: {formatTimestamp(metrics.last_updated_ms)}</span>
      </div>
      <dl className="space-y-2 text-sm">
        <div className="flex items-center justify-between">
          <dt className="text-slate-500">Max drawdown</dt>
          <dd className="font-semibold text-slate-800">
            {formatCurrency(metrics.max_drawdown)}
            {metrics.max_drawdown_pct != null && !Number.isNaN(metrics.max_drawdown_pct) ? (
              <span className="ml-2 text-xs text-slate-500">({formatPercent(metrics.max_drawdown_pct)})</span>
            ) : null}
          </dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-slate-500">Śr. zysk / trade</dt>
          <dd className="font-semibold text-slate-800">{formatCurrency(metrics.avg_profit_per_trade)}</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-slate-500">Win rate</dt>
          <dd className="font-semibold text-slate-800">{formatPercent(metrics.win_rate)}</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-slate-500">Trades</dt>
          <dd className="font-semibold text-slate-800">{formatCount(metrics.trades)}</dd>
        </div>
      </dl>
    </div>
  );
}

export const RiskDashboard: React.FC = () => {
  const { data, error, isLoading } = useSWR<RiskDashboardResp>('/risk/dashboard', fetcher, {
    refreshInterval: 15_000,
  });

  if (error) {
    return (
      <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl p-3">
        Nie udało się wczytać danych ryzyka.
      </div>
    );
  }

  if (isLoading || !data) {
    return (
      <div className="text-sm text-slate-500 bg-slate-50 border border-slate-200 rounded-xl p-3">
        Ładowanie dashboardu ryzyka…
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <MetricsCard title="Backtest" metrics={data.backtest} />
      <MetricsCard title="Live (PnL)" metrics={data.live} />
    </div>
  );
};
