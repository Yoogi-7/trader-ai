import { useMemo } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

export interface AggregatedPnlPoint {
  date: string
  risk_profile: string
  net_pnl_usd: number
  avg_net_pnl_pct?: number | null
  trade_count: number
}

export interface AggregatedExposurePoint {
  date: string
  risk_profile: string
  exposure_usd: number
}

const RISK_PROFILE_ORDER: string[] = ['low', 'medium', 'high']
const RISK_PROFILE_LABELS: Record<string, string> = {
  low: 'Low Risk',
  medium: 'Medium Risk',
  high: 'High Risk',
}
const RISK_PROFILE_COLORS: Record<string, string> = {
  low: '#38bdf8',
  medium: '#a78bfa',
  high: '#f97316',
}

type PivotedDatum = Record<string, number | string>

type PivotKey = 'net_pnl_usd' | 'exposure_usd'

const pivotSeriesByDate = <T extends { date: string; risk_profile: string }>(
  series: T[],
  valueKey: PivotKey,
): PivotedDatum[] => {
  const map = new Map<string, PivotedDatum>()

  series.forEach((point: any) => {
    const isoDate = point.date ? point.date.slice(0, 10) : ''
    if (!isoDate) {
      return
    }

    const current = map.get(isoDate) ?? { date: isoDate }
    current[point.risk_profile] = Number(point[valueKey] ?? 0)
    map.set(isoDate, current)
  })

  const result = Array.from(map.values()).map((entry) => {
    RISK_PROFILE_ORDER.forEach((profile) => {
      if (entry[profile] === undefined) {
        entry[profile] = 0
      }
    })
    return entry
  })

  result.sort((a, b) => String(a.date).localeCompare(String(b.date)))

  return result
}

interface SystemAnalyticsProps {
  pnl: AggregatedPnlPoint[]
  exposure: AggregatedExposurePoint[]
  loading?: boolean
}

const EmptyState = ({ loading }: { loading?: boolean }) => (
  <div className="flex h-full items-center justify-center text-sm text-gray-400">
    {loading ? 'Loading analytics…' : 'No data available yet'}
  </div>
)

export default function SystemAnalytics({ pnl, exposure, loading }: SystemAnalyticsProps) {
  const pnlChartData = useMemo(() => pivotSeriesByDate(pnl, 'net_pnl_usd'), [pnl])
  const exposureChartData = useMemo(
    () => pivotSeriesByDate(exposure, 'exposure_usd'),
    [exposure],
  )

  return (
    <div className="bg-gray-800 rounded-lg p-6 mb-8">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold">System Analytics</h2>
          <p className="text-sm text-gray-400">
            Daily profit &amp; exposure aggregated by risk profile to monitor portfolio health.
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="rounded-lg bg-gray-900 p-4 shadow">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-blue-200">Net PnL (USD)</h3>
            <span className="text-xs uppercase tracking-wide text-gray-500">Daily</span>
          </div>
          <div className="h-64">
            {pnlChartData.length === 0 ? (
              <EmptyState loading={loading} />
            ) : (
              <ResponsiveContainer>
                <LineChart data={pnlChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="date" stroke="#9ca3af" fontSize={12} tickLine={false} />
                  <YAxis stroke="#9ca3af" fontSize={12} tickLine={false} width={80} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#111827', borderRadius: '0.5rem', border: '1px solid #1f2937' }}
                    formatter={(value: number, name: string) => [value.toFixed(2), RISK_PROFILE_LABELS[name] ?? name]}
                  />
                  <Legend formatter={(value) => RISK_PROFILE_LABELS[value] ?? value} />
                  {RISK_PROFILE_ORDER.map((profile) => (
                    <Line
                      key={profile}
                      type="monotone"
                      dataKey={profile}
                      stroke={RISK_PROFILE_COLORS[profile]}
                      strokeWidth={2}
                      dot={false}
                      name={profile}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="rounded-lg bg-gray-900 p-4 shadow">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-purple-200">Capital Exposure (USD)</h3>
            <span className="text-xs uppercase tracking-wide text-gray-500">Daily</span>
          </div>
          <div className="h-64">
            {exposureChartData.length === 0 ? (
              <EmptyState loading={loading} />
            ) : (
              <ResponsiveContainer>
                <AreaChart data={exposureChartData}>
                  <defs>
                    {RISK_PROFILE_ORDER.map((profile) => (
                      <linearGradient
                        key={profile}
                        id={`color-${profile}`}
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop offset="5%" stopColor={RISK_PROFILE_COLORS[profile]} stopOpacity={0.6} />
                        <stop offset="95%" stopColor={RISK_PROFILE_COLORS[profile]} stopOpacity={0.05} />
                      </linearGradient>
                    ))}
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="date" stroke="#9ca3af" fontSize={12} tickLine={false} />
                  <YAxis stroke="#9ca3af" fontSize={12} tickLine={false} width={80} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#111827', borderRadius: '0.5rem', border: '1px solid #1f2937' }}
                    formatter={(value: number, name: string) => [value.toFixed(2), RISK_PROFILE_LABELS[name] ?? name]}
                  />
                  <Legend formatter={(value) => RISK_PROFILE_LABELS[value] ?? value} />
                  {RISK_PROFILE_ORDER.map((profile) => (
                    <Area
                      key={profile}
                      type="monotone"
                      dataKey={profile}
                      stroke={RISK_PROFILE_COLORS[profile]}
                      fill={`url(#color-${profile})`}
                      fillOpacity={1}
                      name={profile}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
