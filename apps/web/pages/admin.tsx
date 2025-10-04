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
}

interface TrainingStatus {
  job_id: string
  status: string
  progress_pct?: number
  current_fold?: number
  total_folds?: number
  accuracy?: number
  hit_rate_tp1?: number
}

export default function Admin() {
  const [backfillJobs, setBackfillJobs] = useState<BackfillStatus[]>([])
  const [trainingJobs, setTrainingJobs] = useState<TrainingStatus[]>([])
  const [activeBackfillId, setActiveBackfillId] = useState<string | null>(null)
  const [activeTrainingId, setActiveTrainingId] = useState<string | null>(null)

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

  const startBackfill = async () => {
    try {
      console.log('Starting backfill, API_URL:', API_URL)
      const response = await axios.post(`${API_URL}/api/v1/backfill/start`, {
        symbol: 'BTC/USDT',
        timeframe: '15m',
        start_date: '2020-01-01T00:00:00',
        end_date: '2024-01-01T00:00:00'
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
            {activeBackfillId ? 'Backfill Running...' : 'Start BTC/USDT Backfill (4 years)'}
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
                    <span>{job.progress_pct.toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-600 rounded-full h-2.5">
                    <div
                      className="bg-blue-500 h-2.5 rounded-full transition-all duration-300"
                      style={{ width: `${job.progress_pct}%` }}
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

                {/* Progress Bar */}
                {job.progress_pct !== undefined && (
                  <div className="mb-2">
                    <div className="flex justify-between text-sm mb-1">
                      <span>Progress</span>
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
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* System Status */}
        <div className="bg-gray-800 rounded-lg p-6">
          <h2 className="text-2xl font-bold mb-4">System Status</h2>
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-gray-700 p-4 rounded">
              <p className="text-gray-400 text-sm">Hit Rate (TP1)</p>
              <p className="text-3xl font-bold text-green-400">57.2%</p>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <p className="text-gray-400 text-sm">Avg Net Profit</p>
              <p className="text-3xl font-bold text-green-400">2.8%</p>
            </div>
            <div className="bg-gray-700 p-4 rounded">
              <p className="text-gray-400 text-sm">Active Models</p>
              <p className="text-3xl font-bold">3</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
