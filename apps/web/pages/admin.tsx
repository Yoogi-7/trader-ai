import { useState, useEffect } from 'react'
import axios from 'axios'

// Use empty string for relative URLs (proxied through Next.js rewrites)
const API_URL = ''

interface BackfillStatus {
  job_id: string
  symbol: string
  timeframe: string
  status: string
  progress_pct: number
  candles_fetched: number
  candles_per_minute?: number
  eta_minutes?: number
  started_at?: string
  completed_at?: string
  created_at?: string
}

interface TrainingStatus {
  job_id: string
  status: string
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
  const [activeTrainingId, setActiveTrainingId] = useState<string | null>(null)
  const [activeSignalGenId, setActiveSignalGenId] = useState<string | null>(null)
  const [showHistoricalSignals, setShowHistoricalSignals] = useState(false)
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [candlesInfo, setCandlesInfo] = useState<CandleInfo[]>([])

  // Load existing jobs on mount
  useEffect(() => {
    const loadJobs = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/v1/backfill/jobs`)
        const jobs: BackfillStatus[] = response.data

        // Filter out jobs older than 24h
        const now = new Date()
        const twentyFourHoursAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000)

        const recentJobs = jobs.filter(job => {
          // Use completed_at for completed jobs, started_at for running, created_at as fallback
          const jobDate = job.completed_at || job.started_at || job.created_at
          if (!jobDate) return true // Keep jobs without timestamp
          return new Date(jobDate) > twentyFourHoursAgo
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

        // Set active job if any is training
        const trainingJob = jobs.find(j => j.status === 'training')
        if (trainingJob) {
          setActiveTrainingId(trainingJob.job_id)
        }
      } catch (error) {
        console.error('Error loading training jobs:', error)
      }
    }

    const loadSignalGenJobs = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/v1/signals/historical/jobs`)
        const jobs: SignalGenerationStatus[] = response.data
        setSignalGenJobs(jobs)

        // Set active job if any is generating
        const genJob = jobs.find(j => j.status === 'generating')
        if (genJob) {
          setActiveSignalGenId(genJob.job_id)
        }
      } catch (error) {
        console.error('Error loading signal generation jobs:', error)
      }
    }

    loadJobs()
    loadTrainingJobs()
    loadSignalGenJobs()
    loadSystemStatus()
    loadCandlesInfo()
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

  // Poll system status every 10 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      loadSystemStatus()
      loadCandlesInfo()
    }, 10000)
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

  // Poll for training status
  useEffect(() => {
    if (!activeTrainingId) return

    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`${API_URL}/api/v1/train/status/${activeTrainingId}`)
        const status: TrainingStatus = response.data

        setTrainingJobs(prev => {
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
          setActiveTrainingId(null)
        }
      } catch (error) {
        console.error('Error fetching training status:', error)
      }
    }, 2000) // Poll every 2 seconds

    return () => clearInterval(interval)
  }, [activeTrainingId])

  // Poll for signal generation status
  useEffect(() => {
    if (!activeSignalGenId) return

    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`${API_URL}/api/v1/signals/historical/status/${activeSignalGenId}`)
        const status: SignalGenerationStatus = response.data

        setSignalGenJobs(prev => {
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
          setActiveSignalGenId(null)
          // Auto-load results when completed
          if (status.status === 'completed') {
            setTimeout(loadHistoricalSignals, 2000)
          }
        }
      } catch (error) {
        console.error('Error fetching signal generation status:', error)
      }
    }, 2000) // Poll every 2 seconds

    return () => clearInterval(interval)
  }, [activeSignalGenId])

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

  const startTraining = async () => {
    try {
      console.log('Starting training, API_URL:', API_URL)
      const response = await axios.post(`${API_URL}/api/v1/train/start`, {
        symbol: 'BTC/USDT',
        timeframe: '15m',
        force_retrain: false
      })
      console.log('Training response:', response.data)
      setActiveTrainingId(response.data.job_id || 'train_' + Date.now())
    } catch (error: any) {
      console.error('Error starting training:', error)
      console.error('Error details:', error.response?.data)
      alert(`Error starting training: ${error.message}`)
    }
  }

  const generateHistoricalSignals = async () => {
    try {
      // Get earliest available date from backfill data
      const infoResponse = await axios.get(`${API_URL}/api/v1/backfill/earliest?symbol=BTC/USDT&timeframe=15m`)
      const earliestDate = infoResponse.data.earliest_date || '2017-01-01T00:00:00'

      const endDate = new Date()

      const response = await axios.post(`${API_URL}/api/v1/signals/historical/generate`, {
        symbol: 'BTC/USDT',
        start_date: earliestDate,
        end_date: endDate.toISOString(),
        timeframe: '15m'
      })

      // Set active job ID to start polling
      setActiveSignalGenId(response.data.job_id)
    } catch (error: any) {
      console.error('Error generating historical signals:', error)
      alert(`Error: ${error.message}`)
    }
  }

  const loadHistoricalSignals = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/v1/signals/historical/results?symbol=BTC/USDT&limit=50`)
      setHistoricalSignals(response.data)
      setShowHistoricalSignals(true)
    } catch (error) {
      console.error('Error loading historical signals:', error)
    }
  }

  const formatETA = (minutes?: number) => {
    if (!minutes) return 'N/A'
    const hours = Math.floor(minutes / 60)
    const mins = Math.floor(minutes % 60)
    return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-4xl font-bold mb-8">TraderAI - Admin Panel</h1>

        {/* Backfill Panel */}
        <div className="bg-gray-800 rounded-lg p-6 mb-8">
          <h2 className="text-2xl font-bold mb-4">Data Backfill</h2>
          <button
            onClick={startBackfill}
            disabled={activeBackfillId !== null}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed px-6 py-2 rounded font-medium"
          >
            {activeBackfillId ? 'Backfill Running...' : 'Start BTC/USDT Backfill (Full History)'}
          </button>

          {/* Active Backfill Jobs */}
          <div className="mt-6 space-y-4">
            {backfillJobs.map((job) => (
              <div key={job.job_id} className="bg-gray-700 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <div>
                    <span className="font-bold">{job.symbol}</span>
                    <span className="text-gray-400 ml-2">{job.timeframe}</span>
                  </div>
                  <div className={`px-3 py-1 rounded text-sm ${
                    job.status === 'completed' ? 'bg-green-600' :
                    job.status === 'running' ? 'bg-blue-600' :
                    job.status === 'failed' ? 'bg-red-600' : 'bg-gray-600'
                  }`}>
                    {job.status.toUpperCase()}
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
                <div className="grid grid-cols-3 gap-4 mt-3 text-sm">
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
                </div>
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
            disabled={activeTrainingId !== null}
            className="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed px-6 py-2 rounded font-medium"
          >
            {activeTrainingId ? 'Training Running...' : 'Train BTC/USDT Model'}
          </button>

          {/* Active Training Jobs */}
          <div className="mt-6 space-y-4">
            {trainingJobs.map((job) => (
              <div key={job.job_id} className="bg-gray-700 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <div className="font-bold">Training Job</div>
                  <div className={`px-3 py-1 rounded text-sm ${
                    job.status === 'completed' ? 'bg-green-600' :
                    job.status === 'training' ? 'bg-blue-600' :
                    job.status === 'failed' ? 'bg-red-600' : 'bg-gray-600'
                  }`}>
                    {job.status.toUpperCase()}
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
              disabled={activeSignalGenId !== null}
              className="bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 disabled:cursor-not-allowed px-6 py-2 rounded font-medium"
            >
              {activeSignalGenId ? 'Generating Signals...' : 'Generate Historical Signals (Full History)'}
            </button>
            <button
              onClick={loadHistoricalSignals}
              className="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded font-medium"
            >
              View Historical Signals
            </button>
          </div>

          {/* Signal Generation Jobs */}
          <div className="space-y-4">
            {signalGenJobs.map((job) => (
              <div key={job.job_id} className="bg-gray-700 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <div>
                    <span className="font-bold">{job.symbol}</span>
                    <span className="text-gray-400 ml-2">Signal Generation</span>
                  </div>
                  <div className={`px-3 py-1 rounded text-sm ${
                    job.status === 'completed' ? 'bg-green-600' :
                    job.status === 'generating' ? 'bg-purple-600' :
                    job.status === 'failed' ? 'bg-red-600' : 'bg-gray-600'
                  }`}>
                    {job.status.toUpperCase()}
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
          {showHistoricalSignals && historicalSignals.length > 0 && (
            <div className="mt-6 space-y-4">
              {historicalSignals.map((signal) => (
                <div key={signal.signal_id} className="bg-gray-700 rounded-lg p-4">
                  <div className="grid grid-cols-5 gap-4 mb-3">
                    <div>
                      <p className="text-xs text-gray-400">Time</p>
                      <p className="text-sm">{new Date(signal.timestamp).toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Symbol</p>
                      <p className="text-sm font-bold">{signal.symbol}</p>
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
              ))}
            </div>
          )}
        </div>

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
                      <span className="text-gray-300">{new Date(info.first_candle).toLocaleDateString()}</span>
                    </div>
                  )}
                  {info.last_candle && (
                    <div className="flex justify-between">
                      <span className="text-gray-400">Last:</span>
                      <span className="text-gray-300">{new Date(info.last_candle).toLocaleDateString()}</span>
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
              <p className="text-3xl font-bold text-green-400">
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
        </div>
      </div>
    </div>
  )
}
