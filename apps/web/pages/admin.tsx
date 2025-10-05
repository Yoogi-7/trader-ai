import { useState, useEffect } from 'react'
import dynamic from 'next/dynamic'
import axios from 'axios'
import type {
  AggregatedExposurePoint,
  AggregatedPnlPoint,
} from '../components/SystemAnalytics'

const SystemAnalytics = dynamic(() => import('../components/SystemAnalytics'), { ssr: false })

// Use empty string for relative URLs (proxied through Next.js rewrites)
const API_URL = ''

const TRACKED_PAIRS = [
  'BTC/USDT',
  'ETH/USDT',
  'BNB/USDT',
  'XRP/USDT',
  'ADA/USDT',
  'SOL/USDT',
  'DOGE/USDT',
  'POL/USDT',
  'DOT/USDT',
  'AVAX/USDT',
  'LINK/USDT',
  'UNI/USDT',
]

interface BackfillStatus {
  job_id: string
  symbol: string
  timeframe: string
  status: string
  progress_pct: number
  candles_fetched: number
  total_candles_estimate?: number
  candles_per_minute?: number
  eta_minutes?: number
  detected_gaps?: { start: string; end: string }[]
  started_at?: string
  completed_at?: string
  created_at?: string
}

interface TrainingStatus {
  job_id: string
  status: string
  symbol?: string
  timeframe?: string
  progress_pct?: number
  labeling_progress_pct?: number
  current_fold?: number
  total_folds?: number
  accuracy?: number
  hit_rate_tp1?: number
  elapsed_seconds?: number
  error_message?: string
}

interface HistoricalSignal {
  signal_id: string
  symbol: string
  side: string
  entry_price: number
  timeframe?: string
  timestamp: string
  confidence: number
  expected_net_profit_pct: number
  ai_summary?: string
  actual_net_pnl_pct?: number
  actual_net_pnl_usd?: number
  final_status?: string
  duration_minutes?: number
  was_profitable?: boolean
}

interface SignalGenerationStatus {
  job_id: string
  status: string
  symbol: string
  timeframe: string
  start_date: string
  end_date: string
  progress_pct?: number
  signals_generated?: number
  signals_backtested?: number
  win_rate?: number
  avg_profit_pct?: number
  elapsed_seconds?: number
  error_message?: string
}

interface SystemStatus {
  hit_rate_tp1?: number
  avg_net_profit_pct?: number
  active_models: number
  total_signals: number
  total_trades: number
  win_rate?: number
  total_net_profit_usd?: number
  avg_trade_duration_minutes?: number
  metrics_source?: string
  metrics_sample_size?: number
}

interface CandleInfo {
  symbol: string
  timeframe: string
  total_candles: number
  first_candle?: string
  last_candle?: string
}

export default function Admin() {
  const [backfillJobs, setBackfillJobs] = useState<BackfillStatus[]>([])
  const [trainingJobs, setTrainingJobs] = useState<TrainingStatus[]>([])
  const [signalGenJobs, setSignalGenJobs] = useState<SignalGenerationStatus[]>([])
  const [historicalSignals, setHistoricalSignals] = useState<HistoricalSignal[]>([])
  const [activeBackfillId, setActiveBackfillId] = useState<string | null>(null)
  const [activeTrainingIds, setActiveTrainingIds] = useState<string[]>([])
  const [activeSignalGenIds, setActiveSignalGenIds] = useState<string[]>([])
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [candlesInfo, setCandlesInfo] = useState<CandleInfo[]>([])
  const [pnlAnalytics, setPnlAnalytics] = useState<AggregatedPnlPoint[]>([])
  const [exposureAnalytics, setExposureAnalytics] = useState<AggregatedExposurePoint[]>([])
  const [analyticsLoading, setAnalyticsLoading] = useState(false)

  // Load existing jobs on mount
  useEffect(() => {
    const loadJobs = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/v1/backfill/jobs`)
        const jobs: BackfillStatus[] = response.data

        // Filter out jobs older than 24h
        const now = new Date()
        const threeHoursAgo = new Date(now.getTime() - 3 * 60 * 60 * 1000)

        const recentJobs = jobs.filter(job => {
          // Use completed_at for completed jobs, started_at for running, created_at as fallback
          const jobDate = job.completed_at || job.started_at || job.created_at
          if (!jobDate) return true // Keep jobs without timestamp
          return new Date(jobDate) > threeHoursAgo
        })

        setBackfillJobs(recentJobs)

        // Set active job if any is running
        const runningJob = recentJobs.find(j => j.status === 'running')
        if (runningJob) {
          setActiveBackfillId(runningJob.job_id)
        }
      } catch (error) {
        console.error('Error loading jobs:', error)
      }
    }

    const loadTrainingJobs = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/v1/train/jobs`)
        const jobs: TrainingStatus[] = response.data
        setTrainingJobs(jobs)

        const activeIds = jobs
          .filter(job => ['training', 'pending', 'queued'].includes(job.status))
          .map(job => job.job_id)
        setActiveTrainingIds(activeIds)
      } catch (error) {
        console.error('Error loading training jobs:', error)
      }
    }

    const loadSignalGenJobs = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/v1/signals/historical/jobs`)
        const jobs: SignalGenerationStatus[] = response.data
        setSignalGenJobs(jobs)

        // Track all active jobs
        const activeIds = jobs
          .filter(job => job.status === 'generating' || job.status === 'pending')
          .map(job => job.job_id)
        setActiveSignalGenIds(activeIds)
      } catch (error) {
        console.error('Error loading signal generation jobs:', error)
      }
    }

    loadJobs()
    loadTrainingJobs()
    loadSignalGenJobs()
    loadSystemStatus()
    loadCandlesInfo()
    loadAnalytics()
    loadHistoricalSignals()
  }, [])

  // Load system status
  const loadSystemStatus = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/v1/system/status`)
      setSystemStatus(response.data)
    } catch (error) {
      console.error('Error loading system status:', error)
    }
  }

  // Load candles info
  const loadCandlesInfo = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/v1/system/candles`)
      setCandlesInfo(response.data)
    } catch (error) {
      console.error('Error loading candles info:', error)
    }
  }

  const loadAnalytics = async () => {
    setAnalyticsLoading(true)
    try {
      const [pnlResponse, exposureResponse] = await Promise.all([
        axios.get(`${API_URL}/api/v1/system/pnl`),
        axios.get(`${API_URL}/api/v1/system/exposure`)
      ])
      setPnlAnalytics(pnlResponse.data)
      setExposureAnalytics(exposureResponse.data)
    } catch (error) {
      console.error('Error loading analytics:', error)
    } finally {
      setAnalyticsLoading(false)
    }
  }

  // Poll system status every 10 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      loadSystemStatus()
      loadCandlesInfo()
    }, 10000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const interval = setInterval(() => {
      loadAnalytics()
    }, 60000)
    return () => clearInterval(interval)
  }, [])

  // Poll for backfill status
  useEffect(() => {
    if (!activeBackfillId) return

    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`${API_URL}/api/v1/backfill/status/${activeBackfillId}`)
        const status: BackfillStatus = response.data

        setBackfillJobs(prev => {
          const existing = prev.findIndex(j => j.job_id === status.job_id)
          if (existing >= 0) {
            const updated = [...prev]
            updated[existing] = status
            return updated
          }
          return [...prev, status]
        })

        // Stop polling if completed or failed
        if (status.status === 'completed' || status.status === 'failed') {
          setActiveBackfillId(null)
        }
      } catch (error) {
        console.error('Error fetching backfill status:', error)
      }
    }, 2000) // Poll every 2 seconds

    return () => clearInterval(interval)
  }, [activeBackfillId])

  // Poll for training status while there are active jobs
  useEffect(() => {
    if (activeTrainingIds.length === 0) return

    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`${API_URL}/api/v1/train/jobs`)
        const jobs: TrainingStatus[] = response.data
        setTrainingJobs(jobs)

        const stillActive = jobs
          .filter(job => ['training', 'pending', 'queued'].includes(job.status))
          .map(job => job.job_id)

        setActiveTrainingIds(prev => {
          if (prev.length === stillActive.length && prev.every(id => stillActive.includes(id))) {
            return prev
          }
          return stillActive
        })
      } catch (error) {
        console.error('Error fetching training status:', error)
      }
    }, 2000) // Poll every 2 seconds

    return () => clearInterval(interval)
  }, [activeTrainingIds.length])

  // Poll for signal generation status
  useEffect(() => {
    if (activeSignalGenIds.length === 0) return

    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`${API_URL}/api/v1/signals/historical/jobs`)
        const jobs: SignalGenerationStatus[] = response.data
        setSignalGenJobs(jobs)

        const activeIds = jobs
          .filter(job => job.status === 'generating' || job.status === 'pending')
          .map(job => job.job_id)

        if (activeIds.length === 0) {
          setActiveSignalGenIds([])
          setTimeout(() => {
            loadHistoricalSignals()
            loadSystemStatus()
          }, 2000)
        } else {
          setActiveSignalGenIds(activeIds)
        }
      } catch (error) {
        console.error('Error fetching signal generation jobs:', error)
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [activeSignalGenIds.length])

  const startBackfill = async () => {
    try {
      console.log('Starting backfill, API_URL:', API_URL)

      // Get earliest available date from backend
      const infoResponse = await axios.get(`${API_URL}/api/v1/backfill/earliest?symbol=BTC/USDT&timeframe=15m`)
      const earliestDate = infoResponse.data.earliest_date || '2017-01-01T00:00:00'

      console.log('Earliest available date:', earliestDate)

      const endDate = new Date().toISOString()

      const response = await axios.post(`${API_URL}/api/v1/backfill/start`, {
        symbol: 'BTC/USDT',
        timeframe: '15m',
        start_date: earliestDate,
        end_date: endDate
      })
      console.log('Backfill response:', response.data)
      setActiveBackfillId(response.data.job_id)
    } catch (error: any) {
      console.error('Error starting backfill:', error)
      console.error('Error details:', error.response?.data)
      alert(`Error starting backfill: ${error.message}`)
    }
  }

  const startAllBackfills = async () => {
    try {
      console.log('Starting backfill for all pairs, API_URL:', API_URL)

      const response = await axios.post(`${API_URL}/api/v1/backfill/start-all`)
      console.log('Backfill all response:', response.data)

      const { jobs_created, jobs_skipped, created } = response.data

      if (jobs_created > 0) {
        alert(`Started ${jobs_created} backfill jobs. Skipped ${jobs_skipped} pairs (already have data).`)
        // Reload jobs list
        const jobsResponse = await axios.get(`${API_URL}/api/v1/backfill/jobs`)
        setBackfillJobs(jobsResponse.data)
      } else {
        alert(`No backfill jobs started. All ${jobs_skipped} pairs already have data.`)
      }
    } catch (error: any) {
      console.error('Error starting all backfills:', error)
      console.error('Error details:', error.response?.data)
      alert(`Error starting backfills: ${error.message}`)
    }
  }

  const cancelBackfill = async (jobId: string) => {
    try {
      await axios.post(`${API_URL}/api/v1/backfill/cancel/${jobId}`)
      alert('Backfill job cancelled')
      // Reload jobs
      const jobsResponse = await axios.get(`${API_URL}/api/v1/backfill/jobs`)
      setBackfillJobs(jobsResponse.data)
      setActiveBackfillId(null)
    } catch (error: any) {
      console.error('Error cancelling backfill:', error)
      alert(`Error: ${error.response?.data?.detail || error.message}`)
    }
  }

  const cancelTraining = async (jobId: string) => {
    try {
      await axios.post(`${API_URL}/api/v1/train/cancel/${jobId}`)
      alert('Training job cancelled')
      // Reload jobs
      const jobsResponse = await axios.get(`${API_URL}/api/v1/train/jobs`)
      const jobs: TrainingStatus[] = jobsResponse.data
      setTrainingJobs(jobs)
      const activeIds = jobs
        .filter(job => ['training', 'pending', 'queued'].includes(job.status))
        .map(job => job.job_id)
      setActiveTrainingIds(activeIds)
    } catch (error: any) {
      console.error('Error cancelling training:', error)
      alert(`Error: ${error.response?.data?.detail || error.message}`)
    }
  }

  const cancelSignalGeneration = async (jobId: string) => {
    try {
      await axios.post(`${API_URL}/api/v1/signals/historical/cancel/${jobId}`)
      alert('Signal generation job cancelled')
      // Reload jobs
      const jobsResponse = await axios.get(`${API_URL}/api/v1/signals/historical/jobs`)
      setSignalGenJobs(jobsResponse.data)
      setActiveSignalGenIds(prev => prev.filter(id => id !== jobId))
    } catch (error: any) {
      console.error('Error cancelling signal generation:', error)
      alert(`Error: ${error.response?.data?.detail || error.message}`)
    }
  }

  const startTraining = async () => {
    try {
      const knownSymbols = candlesInfo.length
        ? Array.from(new Set(candlesInfo.map(info => info.symbol)))
        : TRACKED_PAIRS

      if (knownSymbols.length === 0) {
        alert('No trading pairs configured for training')
        return
      }

      const uniqueSymbols = Array.from(new Set(knownSymbols))

      const launchResults = await Promise.allSettled(
        uniqueSymbols.map(async (symbol) => {
          const response = await axios.post(`${API_URL}/api/v1/train/start`, {
            symbol,
            timeframe: '15m',
            force_retrain: false,
          })

          const jobId: string = response.data.job_id || `train_${symbol.replace('/', '_')}_${Date.now()}`
          const status: string = response.data.status || 'queued'

          return {
            job_id: jobId,
            status,
            symbol: response.data.symbol || symbol,
            timeframe: response.data.timeframe || '15m',
            progress_pct: 0,
            labeling_progress_pct: 0,
          } as TrainingStatus
        })
      )

      const successfulLaunches: TrainingStatus[] = []
      const failedLaunches: { symbol: string; reason: string }[] = []

      launchResults.forEach((result, index) => {
        const symbol = uniqueSymbols[index]
        if (result.status === 'fulfilled') {
          successfulLaunches.push(result.value)
        } else {
          const failure: any = result
          const reason =
            failure?.reason?.response?.data?.detail ||
            failure?.reason?.message ||
            (typeof failure?.reason === 'string' ? failure.reason : 'Unknown error')
          failedLaunches.push({ symbol, reason })
        }
      })

      if (successfulLaunches.length === 0) {
        const combinedReason = failedLaunches.map(item => `${item.symbol}: ${item.reason}`).join('\n')
        throw new Error(combinedReason || 'Failed to start training jobs')
      }

      setTrainingJobs(prev => {
        const merged = new Map(prev.map(job => [job.job_id, job]))
        successfulLaunches.forEach(job => {
          merged.set(job.job_id, { ...merged.get(job.job_id), ...job })
        })
        return Array.from(merged.values())
      })

      setActiveTrainingIds(prev => {
        const combined = [...prev, ...successfulLaunches.map(job => job.job_id)]
        return Array.from(new Set(combined))
      })

      if (failedLaunches.length > 0) {
        const message = failedLaunches.map(item => `${item.symbol}: ${item.reason}`).join('\n')
        alert(`Some training jobs failed to start:\n${message}`)
      }
    } catch (error: any) {
      console.error('Error starting training:', error)
      alert(`Error starting training: ${error.response?.data?.detail || error.message}`)
    }
  }

  const normalizeToIsoUtc = (value: string | null | undefined) => {
    if (!value) {
      return new Date('2017-01-01T00:00:00Z').toISOString()
    }

    const trimmed = value.trim()
    const hasTimezone = /([zZ]|[+-]\d\d:\d\d)$/.test(trimmed)
    const candidate = hasTimezone ? trimmed : `${trimmed}Z`
    const parsed = new Date(candidate)

    if (Number.isNaN(parsed.getTime())) {
      return new Date('2017-01-01T00:00:00Z').toISOString()
    }

    return parsed.toISOString()
  }

  const generateHistoricalSignals = async () => {
    try {
      const knownSymbols = candlesInfo.length
        ? Array.from(new Set(candlesInfo.map(info => info.symbol)))
        : TRACKED_PAIRS

      if (knownSymbols.length === 0) {
        alert('No trading pairs configured for historical generation')
        return
      }

      const endDateIso = new Date().toISOString()

      const earliestBySymbol = await Promise.all(
        knownSymbols.map(async (symbol) => {
          try {
            const response = await axios.get(`${API_URL}/api/v1/backfill/earliest`, {
              params: { symbol, timeframe: '15m' },
            })
            return {
              symbol,
              start: response.data.earliest_date || '2017-01-01T00:00:00Z',
            }
          } catch (error) {
            console.error(`Failed to load earliest backfill for ${symbol}`, error)
            return { symbol, start: '2017-01-01T00:00:00Z' }
          }
        })
      )

      const jobLaunches = await Promise.all(
        earliestBySymbol.map(async ({ symbol, start }) => {
          const normalizedStart = normalizeToIsoUtc(start)

          const response = await axios.post(`${API_URL}/api/v1/signals/historical/generate`, {
            symbol,
            start_date: normalizedStart,
            end_date: endDateIso,
            timeframe: '15m',
          })

          const placeholderStatus = response.data.status && response.data.status !== 'queued'
            ? response.data.status
            : 'generating'

          return {
            symbol,
            startDate: normalizedStart,
            jobId: response.data.job_id as string,
            status: placeholderStatus as string,
          }
        })
      )

      const activeIds = jobLaunches.map(job => job.jobId)
      setActiveSignalGenIds(activeIds)

      setSignalGenJobs(prev => {
        const filtered = prev.filter(job => !activeIds.includes(job.job_id))
        const placeholders: SignalGenerationStatus[] = jobLaunches.map(job => ({
          job_id: job.jobId,
          status: job.status,
          symbol: job.symbol,
          timeframe: '15m',
          start_date: job.startDate,
          end_date: endDateIso,
          progress_pct: 0,
          signals_generated: 0,
          signals_backtested: 0,
        }))
        return [...placeholders, ...filtered]
      })

      // Refresh existing data while jobs run
      loadHistoricalSignals()
      loadSystemStatus()
    } catch (error: any) {
      console.error('Error generating historical signals:', error)
      alert(`Error: ${error.message}`)
    }
  }

  const loadHistoricalSignals = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/v1/signals/historical/results?limit=150`)
      setHistoricalSignals(response.data)
    } catch (error) {
      console.error('Error loading historical signals:', error)
    }
  }

  const formatETA = (minutes?: number) => {
    if (minutes === undefined || minutes === null) return 'N/A'
    const hours = Math.floor(minutes / 60)
    const mins = Math.floor(minutes % 60)
    return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`
  }

  const formatGapTimestamp = (iso?: string) => {
    if (!iso) return 'Unknown'
    const date = new Date(iso)
    return isNaN(date.getTime()) ? iso : date.toLocaleString()
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-4xl font-bold mb-8">TraderAI - Admin Panel</h1>

        {/* Backfill Panel */}
        <div className="bg-gray-800 rounded-lg p-6 mb-8">
          <h2 className="text-2xl font-bold mb-4">Data Backfill</h2>
          <div className="flex gap-4 mb-6">
            <button
              onClick={startBackfill}
              disabled={activeBackfillId !== null}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed px-6 py-2 rounded font-medium"
            >
              {activeBackfillId ? 'Backfill Running...' : 'Start BTC/USDT Backfill (Full History)'}
            </button>
            <button
              onClick={startAllBackfills}
              className="bg-purple-600 hover:bg-purple-700 px-6 py-2 rounded font-medium"
            >
              Start All Pairs Backfill (12 pairs)
            </button>
          </div>

          {/* Active Backfill Jobs */}
          <div className="mt-6 space-y-4">
            {backfillJobs.map((job) => (
              <div key={job.job_id} className="bg-gray-700 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <div>
                    <span className="font-bold">{job.symbol}</span>
                    <span className="text-gray-400 ml-2">{job.timeframe}</span>
                  </div>
                  <div className="flex gap-2 items-center">
                    <div className={`px-3 py-1 rounded text-sm ${
                      job.status === 'completed' ? 'bg-green-600' :
                      job.status === 'running' ? 'bg-blue-600' :
                      job.status === 'failed' ? 'bg-red-600' : 'bg-gray-600'
                    }`}>
                      {job.status.toUpperCase()}
                    </div>
                    {(job.status === 'running' || job.status === 'pending') && (
                      <button
                        onClick={() => cancelBackfill(job.job_id)}
                        className="px-3 py-1 bg-red-600 hover:bg-red-700 rounded text-sm"
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </div>

                {/* Progress Bar */}
                <div className="mb-2">
                  <div className="flex justify-between text-sm mb-1">
                    <span>Progress</span>
                    <span>{job.progress_pct !== null && job.progress_pct !== undefined ? job.progress_pct.toFixed(1) : '0.0'}%</span>
                  </div>
                  <div className="w-full bg-gray-600 rounded-full h-2.5">
                    <div
                      className="bg-blue-500 h-2.5 rounded-full transition-all duration-300"
                      style={{ width: `${job.progress_pct ?? 0}%` }}
                    ></div>
                  </div>
                </div>

                {/* Stats */}
                {job.status !== 'failed' && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-3 text-sm">
                    <div>
                      <p className="text-gray-400">Candles Fetched</p>
                      <p className="font-bold">{job.candles_fetched.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-gray-400">Speed</p>
                      <p className="font-bold">{job.candles_per_minute?.toFixed(0) || 'N/A'} c/min</p>
                    </div>
                    <div>
                      <p className="text-gray-400">ETA</p>
                      <p className="font-bold">{formatETA(job.eta_minutes)}</p>
                    </div>
                    {job.total_candles_estimate !== undefined && (
                      <div>
                        <p className="text-gray-400">Est. Total</p>
                        <p className="font-bold">{job.total_candles_estimate.toLocaleString()}</p>
                      </div>
                    )}
                  </div>
                )}

                {job.detected_gaps && job.detected_gaps.length > 0 && (
                  <div className="mt-4 rounded border border-yellow-600/60 bg-yellow-900/20 p-3 text-xs space-y-2">
                    <p className="text-yellow-300 font-semibold">Detected Data Gaps ({job.detected_gaps.length})</p>
                    <ul className="space-y-1">
                      {job.detected_gaps.slice(0, 3).map((gap, index) => (
                        <li key={`${job.job_id}-gap-${index}`} className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-1">
                          <span className="text-yellow-200">Gap #{index + 1}</span>
                          <span className="text-gray-200">
                            {formatGapTimestamp(gap.start)}
                            <span className="mx-1 text-gray-400">→</span>
                            {formatGapTimestamp(gap.end)}
                          </span>
                        </li>
                      ))}
                      {job.detected_gaps.length > 3 && (
                        <li className="text-gray-400">+{job.detected_gaps.length - 3} more gap{job.detected_gaps.length - 3 === 1 ? '' : 's'} detected</li>
                      )}
                    </ul>
                  </div>
                )}

                {/* Error Message */}
                {job.status === 'failed' && (
                  <div className="mt-3 p-3 bg-red-900 border border-red-700 rounded text-sm">
                    <p className="text-red-200 font-semibold">Error:</p>
                    <p className="text-red-300">Job failed. Please check logs or try again.</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Training Panel */}
        <div className="bg-gray-800 rounded-lg p-6 mb-8">
          <h2 className="text-2xl font-bold mb-4">Model Training</h2>
          <p className="text-gray-400 mb-4">
            Train ML models using walk-forward validation with purge & embargo.
          </p>
          <button
            onClick={startTraining}
            disabled={activeTrainingIds.length > 0}
            className="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed px-6 py-2 rounded font-medium"
          >
            {activeTrainingIds.length > 0 ? 'Training Running...' : 'Train All Models'}
          </button>

          {/* Active Training Jobs */}
          <div className="mt-6 space-y-4">
            {trainingJobs.map((job) => (
              <div key={job.job_id} className="bg-gray-700 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <div>
                    <div className="font-bold">{job.symbol || 'Training Job'}</div>
                    {job.timeframe && (
                      <div className="text-sm text-gray-300">{job.timeframe}</div>
                    )}
                  </div>
                  <div className="flex gap-2 items-center">
                    <div className={`px-3 py-1 rounded text-sm ${
                      job.status === 'completed' ? 'bg-green-600' :
                      job.status === 'training' ? 'bg-blue-600' :
                      job.status === 'failed' ? 'bg-red-600' : 'bg-gray-600'
                    }`}>
                      {job.status.toUpperCase()}
                    </div>
                    {(job.status === 'training' || job.status === 'pending' || job.status === 'queued') && (
                      <button
                        onClick={() => cancelTraining(job.job_id)}
                        className="px-3 py-1 bg-red-600 hover:bg-red-700 rounded text-sm"
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </div>

                {/* Labeling Progress Bar */}
                {job.status === 'training' && job.labeling_progress_pct !== undefined && job.labeling_progress_pct !== null && job.labeling_progress_pct < 100 && (
                  <div className="mb-2">
                    <div className="flex justify-between text-sm mb-1">
                      <span>Preparing Data (Labeling)</span>
                      <span>{job.labeling_progress_pct.toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-gray-600 rounded-full h-2.5">
                      <div
                        className="bg-blue-400 h-2.5 rounded-full transition-all duration-300"
                        style={{ width: `${job.labeling_progress_pct}%` }}
                      ></div>
                    </div>
                  </div>
                )}

                {/* Training Progress Bar */}
                {job.progress_pct !== undefined && job.progress_pct !== null && job.progress_pct > 0 && (
                  <div className="mb-2">
                    <div className="flex justify-between text-sm mb-1">
                      <span>Training Progress</span>
                      <span>{job.progress_pct.toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-gray-600 rounded-full h-2.5">
                      <div
                        className="bg-green-500 h-2.5 rounded-full transition-all duration-300"
                        style={{ width: `${job.progress_pct}%` }}
                      ></div>
                    </div>
                  </div>
                )}

                {/* Stats */}
                <div className="grid grid-cols-2 gap-4 mt-3 text-sm">
                  {job.current_fold !== undefined && job.total_folds !== undefined && (
                    <div>
                      <p className="text-gray-400">Fold</p>
                      <p className="font-bold">{job.current_fold} / {job.total_folds}</p>
                    </div>
                  )}
                  {job.accuracy !== undefined && (
                    <div>
                      <p className="text-gray-400">Accuracy</p>
                      <p className="font-bold text-green-400">{(job.accuracy * 100).toFixed(1)}%</p>
                    </div>
                  )}
                  {job.hit_rate_tp1 !== undefined && (
                    <div>
                      <p className="text-gray-400">Hit Rate TP1</p>
                      <p className="font-bold text-green-400">{(job.hit_rate_tp1 * 100).toFixed(1)}%</p>
                    </div>
                  )}
                  {job.elapsed_seconds !== undefined && (
                    <div>
                      <p className="text-gray-400">Elapsed Time</p>
                      <p className="font-bold">{Math.floor(job.elapsed_seconds / 60)}m {Math.floor(job.elapsed_seconds % 60)}s</p>
                    </div>
                  )}
                </div>

                {/* Error Message */}
                {job.error_message && (
                  <div className="mt-3 p-3 bg-red-900 border border-red-700 rounded text-sm">
                    <p className="text-red-200 font-semibold">Error:</p>
                    <p className="text-red-300">{job.error_message}</p>
                  </div>
                )}

                {/* Job ID for debugging */}
                <div className="mt-3 text-xs text-gray-500">
                  Job ID: {job.job_id}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Historical Signals Generation */}
        <div className="bg-gray-800 rounded-lg p-6 mb-8">
          <h2 className="text-2xl font-bold mb-4">Historical Signal Analysis</h2>
          <p className="text-gray-400 mb-4">
            Generate and analyze historical signals to validate strategy performance.
          </p>
          <div className="flex gap-4 mb-6">
            <button
              onClick={generateHistoricalSignals}
              disabled={activeSignalGenIds.length > 0}
              className="bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 disabled:cursor-not-allowed px-6 py-2 rounded font-medium"
            >
              {activeSignalGenIds.length > 0 ? 'Generating Signals...' : 'Generate Historical Signals (All Pairs)'}
            </button>
          </div>

          {/* Signal Generation Jobs */}
          <div className="space-y-4">
            {signalGenJobs.map((job) => (
              <div key={job.job_id} className="bg-gray-700 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <div>
                    <span className="font-bold">{job.symbol}</span>
                    <span className="text-gray-400 ml-2">{job.timeframe}</span>
                    <span className="text-gray-400 ml-2">Signal Generation</span>
                  </div>
                  <div className="flex gap-2 items-center">
                    <div className={`px-3 py-1 rounded text-sm ${
                      job.status === 'completed' ? 'bg-green-600' :
                      job.status === 'generating' ? 'bg-purple-600' :
                      job.status === 'failed' ? 'bg-red-600' : 'bg-gray-600'
                    }`}>
                      {job.status.toUpperCase()}
                    </div>
                    {(job.status === 'generating' || job.status === 'pending') && (
                      <button
                        onClick={() => cancelSignalGeneration(job.job_id)}
                        className="px-3 py-1 bg-red-600 hover:bg-red-700 rounded text-sm"
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </div>

                {/* Progress Bar */}
                {job.progress_pct !== undefined && job.progress_pct !== null && (
                  <div className="mb-2">
                    <div className="flex justify-between text-sm mb-1">
                      <span>Progress</span>
                      <span>{job.progress_pct.toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-gray-600 rounded-full h-2.5">
                      <div
                        className="bg-purple-500 h-2.5 rounded-full transition-all duration-300"
                        style={{ width: `${job.progress_pct}%` }}
                      ></div>
                    </div>
                  </div>
                )}

                {/* Stats */}
                <div className="grid grid-cols-3 gap-4 mt-3 text-sm">
                  {job.signals_generated !== undefined && (
                    <div>
                      <p className="text-gray-400">Signals Generated</p>
                      <p className="font-bold text-purple-400">{job.signals_generated}</p>
                    </div>
                  )}
                  {job.signals_backtested !== undefined && (
                    <div>
                      <p className="text-gray-400">Backtested</p>
                      <p className="font-bold text-purple-400">{job.signals_backtested}</p>
                    </div>
                  )}
                  {job.win_rate !== undefined && job.win_rate !== null && (
                    <div>
                      <p className="text-gray-400">Win Rate</p>
                      <p className="font-bold text-green-400">{(job.win_rate * 100).toFixed(1)}%</p>
                    </div>
                  )}
                  {job.elapsed_seconds !== undefined && (
                    <div>
                      <p className="text-gray-400">Elapsed Time</p>
                      <p className="font-bold">{Math.floor(job.elapsed_seconds / 60)}m {Math.floor(job.elapsed_seconds % 60)}s</p>
                    </div>
                  )}
                </div>

                {/* Error Message */}
                {job.error_message && (
                  <div className="mt-3 p-3 bg-red-900 border border-red-700 rounded text-sm">
                    <p className="text-red-200 font-semibold">Error:</p>
                    <p className="text-red-300">{job.error_message}</p>
                  </div>
                )}

                {/* Job ID */}
                <div className="mt-3 text-xs text-gray-500">
                  Job ID: {job.job_id}
                </div>
              </div>
            ))}
          </div>

          {/* Historical Signals Table */}
          <div className="mt-6 space-y-4">
            {historicalSignals.length === 0 ? (
              <div className="bg-gray-700 rounded-lg p-4 text-sm text-gray-300">
                No historical signals available yet. Generate to populate this section.
              </div>
            ) : (
              historicalSignals.map((signal) => (
                <div key={signal.signal_id} className="bg-gray-700 rounded-lg p-4">
                  <div className="grid grid-cols-5 gap-4 mb-3">
                    <div>
                      <p className="text-xs text-gray-400">Time</p>
                      <p className="text-sm">{new Date(signal.timestamp).toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Symbol</p>
                      <p className="text-sm font-bold">
                        {signal.symbol}
                        {signal.timeframe ? ` (${signal.timeframe})` : ''}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Side</p>
                      <span className={`px-2 py-1 rounded text-xs ${
                        signal.side === 'LONG' ? 'bg-green-600' : 'bg-red-600'
                      }`}>
                        {signal.side}
                      </span>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Entry</p>
                      <p className="text-sm">${signal.entry_price.toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Status</p>
                      {signal.final_status && (
                        <span className={`px-2 py-1 rounded text-xs ${
                          signal.final_status.includes('tp') ? 'bg-green-600' :
                          signal.final_status === 'sl_hit' ? 'bg-red-600' :
                          'bg-gray-600'
                        }`}>
                          {signal.final_status}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-4 gap-4 mb-3 text-sm">
                    <div>
                      <p className="text-xs text-gray-400">Expected Profit</p>
                      <p className="text-gray-300">{signal.expected_net_profit_pct.toFixed(2)}%</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Actual %</p>
                      <p className={`font-bold ${
                        signal.was_profitable === true ? 'text-green-400' :
                        signal.was_profitable === false ? 'text-red-400' : 'text-gray-400'
                      }`}>
                        {signal.actual_net_pnl_pct !== null && signal.actual_net_pnl_pct !== undefined
                          ? `${signal.actual_net_pnl_pct.toFixed(2)}%`
                          : 'N/A'}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Actual $</p>
                      <p className={`font-bold ${
                        signal.was_profitable === true ? 'text-green-400' :
                        signal.was_profitable === false ? 'text-red-400' : 'text-gray-400'
                      }`}>
                        {signal.actual_net_pnl_usd !== null && signal.actual_net_pnl_usd !== undefined
                          ? `$${signal.actual_net_pnl_usd.toFixed(2)}`
                          : 'N/A'}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Duration</p>
                      <p className="text-gray-300">{signal.duration_minutes ? `${signal.duration_minutes}m` : 'N/A'}</p>
                    </div>
                  </div>

                  {signal.ai_summary && (
                    <div className="mt-3 p-3 bg-gray-800 rounded border-l-4 border-blue-500">
                      <p className="text-xs text-blue-400 font-semibold mb-1">🤖 AI Analysis</p>
                      <p className="text-sm text-gray-300">{signal.ai_summary}</p>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        <SystemAnalytics
          pnl={pnlAnalytics}
          exposure={exposureAnalytics}
          loading={analyticsLoading}
        />

        {/* Database Candles Info */}
        <div className="bg-gray-800 rounded-lg p-6 mb-8">
          <h2 className="text-2xl font-bold mb-4">Database Status - Trading Pairs</h2>
          <div className="grid grid-cols-2 gap-4">
            {candlesInfo.map((info) => (
              <div key={info.symbol} className="bg-gray-700 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="text-lg font-bold">{info.symbol}</h3>
                  <span className="text-sm text-gray-400">{info.timeframe}</span>
                </div>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Total Candles:</span>
                    <span className="font-bold text-blue-400">{info.total_candles.toLocaleString()}</span>
                  </div>
                  {info.first_candle && (
                    <div className="flex justify-between">
                      <span className="text-gray-400">First:</span>
                      <span className="text-gray-300">{new Date(info.first_candle).toLocaleString()}</span>
                    </div>
                  )}
                  {info.last_candle && (
                    <div className="flex justify-between">
                      <span className="text-gray-400">Last:</span>
                      <span className="text-gray-300">{new Date(info.last_candle).toLocaleString()}</span>
                    </div>
                  )}
                  {!info.first_candle && !info.last_candle && (
                    <div className="text-gray-500 text-center">No data</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* System Status */}
        <div className="bg-gray-800 rounded-lg p-6">
          <h2 className="text-2xl font-bold mb-4">System Metrics</h2>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="bg-gray-700 p-4 rounded">
              <p className="text-gray-400 text-sm">Hit Rate (TP1)</p>
              <p className="text-3xl font-bold text-green-400">
                {systemStatus && systemStatus.hit_rate_tp1 !== null && systemStatus.hit_rate_tp1 !== undefined
                  ? `${(systemStatus.hit_rate_tp1 * 100).toFixed(1)}%`
                  : 'N/A'}
              </p>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <p className="text-gray-400 text-sm">Avg Net Profit</p>
              <p
                className={`text-3xl font-bold ${
                  systemStatus && systemStatus.avg_net_profit_pct !== null && systemStatus.avg_net_profit_pct !== undefined
                    ? systemStatus.avg_net_profit_pct >= 0
                      ? 'text-green-400'
                      : 'text-red-400'
                    : 'text-gray-400'
                }`}
              >
                {systemStatus && systemStatus.avg_net_profit_pct !== null && systemStatus.avg_net_profit_pct !== undefined
                  ? `${systemStatus.avg_net_profit_pct.toFixed(1)}%`
                  : 'N/A'}
              </p>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <p className="text-gray-400 text-sm">Active Models</p>
              <p className="text-3xl font-bold">{systemStatus?.active_models ?? 0}</p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-gray-700 p-4 rounded">
              <p className="text-gray-400 text-sm">Total Signals</p>
              <p className="text-2xl font-bold">{systemStatus?.total_signals ?? 0}</p>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <p className="text-gray-400 text-sm">Total Trades</p>
              <p className="text-2xl font-bold">{systemStatus?.total_trades ?? 0}</p>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <p className="text-gray-400 text-sm">Win Rate</p>
              <p className="text-2xl font-bold text-green-400">
                {systemStatus && systemStatus.win_rate !== null && systemStatus.win_rate !== undefined
                  ? `${(systemStatus.win_rate * 100).toFixed(1)}%`
                  : 'N/A'}
              </p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4 mt-4">
            <div className="bg-gray-700 p-4 rounded">
              <p className="text-gray-400 text-sm">Total Net Profit</p>
              <p
                className={`text-2xl font-bold ${
                  systemStatus && systemStatus.total_net_profit_usd !== null && systemStatus.total_net_profit_usd !== undefined
                    ? systemStatus.total_net_profit_usd >= 0
                      ? 'text-green-400'
                      : 'text-red-400'
                    : 'text-gray-400'
                }`}
              >
                {systemStatus && systemStatus.total_net_profit_usd !== null && systemStatus.total_net_profit_usd !== undefined
                  ? `$${systemStatus.total_net_profit_usd.toFixed(2)}`
                  : 'N/A'}
              </p>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <p className="text-gray-400 text-sm">Avg Trade Duration</p>
              <p className="text-2xl font-bold">
                {systemStatus && systemStatus.avg_trade_duration_minutes !== null && systemStatus.avg_trade_duration_minutes !== undefined
                  ? formatETA(systemStatus.avg_trade_duration_minutes)
                  : 'N/A'}
              </p>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <p className="text-gray-400 text-sm">Metrics Sample Size</p>
              <p className="text-2xl font-bold">{systemStatus?.metrics_sample_size ?? 0}</p>
            </div>
          </div>
          {systemStatus?.metrics_source && (
            <p className="text-xs text-gray-500 mt-3">
              Metrics based on {systemStatus.metrics_source.replace(/_/g, ' ')} ({systemStatus.metrics_sample_size ?? 0} samples).
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
