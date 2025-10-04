import { useState } from 'react'
import axios from 'axios'

const API_URL = process.env.API_URL || 'http://localhost:8000'

export default function Admin() {
  const [backfillStatus, setBackfillStatus] = useState<any>(null)

  const startBackfill = async () => {
    try {
      const response = await axios.post(`${API_URL}/api/v1/backfill/start`, {
        symbol: 'BTC/USDT',
        timeframe: '15m',
        start_date: '2020-01-01T00:00:00',
        end_date: '2024-01-01T00:00:00'
      })
      alert(`Backfill started: ${response.data.job_id}`)
    } catch (error) {
      console.error('Error starting backfill:', error)
    }
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
            className="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded font-medium"
          >
            Start BTC/USDT Backfill (4 years)
          </button>

          {backfillStatus && (
            <div className="mt-4 p-4 bg-gray-700 rounded">
              <p>Status: {backfillStatus.status}</p>
              <p>Progress: {backfillStatus.progress_pct}%</p>
            </div>
          )}
        </div>

        {/* Training Panel */}
        <div className="bg-gray-800 rounded-lg p-6 mb-8">
          <h2 className="text-2xl font-bold mb-4">Model Training</h2>
          <p className="text-gray-400 mb-4">
            Train ML models using walk-forward validation with purge & embargo.
          </p>
          <button className="bg-green-600 hover:bg-green-700 px-6 py-2 rounded font-medium">
            Train BTC/USDT Model
          </button>
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
