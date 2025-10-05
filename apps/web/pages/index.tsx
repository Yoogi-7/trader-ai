import { useState, useEffect, useCallback, useRef } from 'react'
import axios from 'axios'

const API_URL = process.env.API_URL || 'http://localhost:8000'

interface Signal {
  signal_id: string
  symbol: string
  side: string
  entry_price: number
  tp1_price: number
  tp2_price: number
  tp3_price: number
  sl_price: number
  leverage: number
  confidence: number
  expected_net_profit_pct: number
  risk_profile: string
  timestamp: string
}

export default function Home() {
  const [riskProfile, setRiskProfile] = useState('MEDIUM')
  const [capital, setCapital] = useState(100)
  const { signals } = useLiveSignals(riskProfile)

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-4xl font-bold mb-8">TraderAI - Live Signals</h1>

        {/* Controls */}
        <div className="bg-gray-800 rounded-lg p-6 mb-8">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Risk Profile</label>
              <select
                value={riskProfile}
                onChange={(e) => setRiskProfile(e.target.value)}
                className="w-full bg-gray-700 rounded px-4 py-2"
              >
                <option value="LOW">Low Risk</option>
                <option value="MEDIUM">Medium Risk</option>
                <option value="HIGH">High Risk</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Capital (USD)</label>
              <input
                type="number"
                value={capital}
                onChange={(e) => setCapital(Number(e.target.value))}
                className="w-full bg-gray-700 rounded px-4 py-2"
              />
            </div>
          </div>
        </div>

        {/* Signals Table */}
        <div className="bg-gray-800 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-700">
              <tr>
                <th className="px-4 py-3 text-left">Symbol</th>
                <th className="px-4 py-3 text-left">Side</th>
                <th className="px-4 py-3 text-left">Entry</th>
                <th className="px-4 py-3 text-left">TP1/TP2/TP3</th>
                <th className="px-4 py-3 text-left">SL</th>
                <th className="px-4 py-3 text-left">Leverage</th>
                <th className="px-4 py-3 text-left">Confidence</th>
                <th className="px-4 py-3 text-left">Expected Profit</th>
              </tr>
            </thead>
            <tbody>
              {signals.map((signal) => (
                <tr key={signal.signal_id} className="border-t border-gray-700 hover:bg-gray-750">
                  <td className="px-4 py-3 font-medium">{signal.symbol}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded text-xs ${
                      signal.side === 'LONG' ? 'bg-green-600' : 'bg-red-600'
                    }`}>
                      {signal.side}
                    </span>
                  </td>
                  <td className="px-4 py-3">${signal.entry_price.toFixed(2)}</td>
                  <td className="px-4 py-3 text-sm">
                    ${signal.tp1_price.toFixed(2)} / ${signal.tp2_price.toFixed(2)} / ${signal.tp3_price.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-red-400">${signal.sl_price.toFixed(2)}</td>
                  <td className="px-4 py-3">{signal.leverage.toFixed(1)}x</td>
                  <td className="px-4 py-3">{(signal.confidence * 100).toFixed(1)}%</td>
                  <td className="px-4 py-3 text-green-400">+{signal.expected_net_profit_pct.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>

          {signals.length === 0 && (
            <div className="text-center py-12 text-gray-400">
              No active signals for selected risk profile
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function useLiveSignals(riskProfile: string) {
  const [signals, setSignals] = useState<Signal[]>([])
  const websocketRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const shouldReconnectRef = useRef(true)
  const hasReceivedMessageRef = useRef(false)
  const isMountedRef = useRef(false)

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  const fetchSignals = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/api/v1/signals/live`, {
        params: { risk_profile: riskProfile.toLowerCase() }
      })
      if (isMountedRef.current) {
        setSignals(response.data)
      }
    } catch (error) {
      console.error('Error fetching signals:', error)
    }
  }, [riskProfile])

  useEffect(() => {
    fetchSignals()
  }, [fetchSignals])

  const connectWebSocket = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    hasReceivedMessageRef.current = false

    const baseUrl = API_URL.replace(/^http/, 'ws').replace(/\/$/, '')
    const url = `${baseUrl}/ws/signals?risk_profile=${riskProfile.toLowerCase()}`
    const socket = new WebSocket(url)
    websocketRef.current = socket

    const handleMessage = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data)
        hasReceivedMessageRef.current = true

        if (Array.isArray(payload)) {
          if (isMountedRef.current) {
            setSignals(payload)
          }
        } else if (payload && typeof payload === 'object' && 'signal_id' in payload) {
          setSignals((prevSignals) => {
            if (!isMountedRef.current) {
              return prevSignals
            }

            const existingIndex = prevSignals.findIndex(
              (signal) => signal.signal_id === (payload as Signal).signal_id
            )

            if (existingIndex >= 0) {
              const updatedSignals = [...prevSignals]
              updatedSignals[existingIndex] = payload as Signal
              return updatedSignals
            }

            return [payload as Signal, ...prevSignals]
          })
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error)
      }
    }

    const scheduleReconnect = () => {
      if (!shouldReconnectRef.current) {
        return
      }

      reconnectTimeoutRef.current = setTimeout(() => {
        connectWebSocket()
      }, 3000)

      if (!hasReceivedMessageRef.current) {
        fetchSignals()
      }
    }

    socket.addEventListener('open', () => {
      if (!hasReceivedMessageRef.current) {
        fetchSignals()
      }
    })
    socket.addEventListener('message', handleMessage)
    socket.addEventListener('close', scheduleReconnect)
    socket.addEventListener('error', (event) => {
      console.error('WebSocket error:', event)
      socket.close()
    })
  }, [fetchSignals, riskProfile])

  useEffect(() => {
    shouldReconnectRef.current = true
    hasReceivedMessageRef.current = false
    connectWebSocket()

    return () => {
      shouldReconnectRef.current = false
      hasReceivedMessageRef.current = false

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }

      if (websocketRef.current) {
        websocketRef.current.close()
        websocketRef.current = null
      }
    }
  }, [connectWebSocket])

  return { signals }
}
