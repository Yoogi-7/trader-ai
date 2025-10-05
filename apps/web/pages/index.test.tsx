import { render, screen, waitFor, act } from '@testing-library/react'
import axios from 'axios'
import Home from './index'

type AxiosMock = jest.Mocked<typeof axios>

jest.mock('axios')

class MockWebSocket {
  static instances: MockWebSocket[] = []
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  url: string
  readyState = MockWebSocket.CONNECTING
  private listeners: Record<string, Set<(event: any) => void>> = {
    open: new Set(),
    message: new Set(),
    close: new Set(),
    error: new Set()
  }

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  addEventListener(type: string, listener: (event: any) => void) {
    this.listeners[type]?.add(listener)
  }

  removeEventListener(type: string, listener: (event: any) => void) {
    this.listeners[type]?.delete(listener)
  }

  close() {
    this.readyState = MockWebSocket.CLOSED
    this.emit('close', new Event('close'))
  }

  send() {
    // no-op for tests
  }

  emit(type: 'open' | 'message' | 'close' | 'error', event: any) {
    if (type === 'open') {
      this.readyState = MockWebSocket.OPEN
    }

    this.listeners[type]?.forEach((listener) => listener(event))
  }

  static reset() {
    MockWebSocket.instances = []
  }
}

describe('Home page', () => {
  const mockedAxios = axios as AxiosMock
  let consoleErrorSpy: jest.SpyInstance

  beforeEach(() => {
    MockWebSocket.reset()
    ;(global as any).WebSocket = MockWebSocket
    mockedAxios.get.mockResolvedValue({ data: [] })

    const originalConsoleError = console.error
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation((...args: unknown[]) => {
      if (typeof args[0] === 'string' && args[0].includes('act(...)')) {
        return
      }

      originalConsoleError(...(args as Parameters<typeof console.error>))
    })
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
    jest.clearAllMocks()
  })

  it('renders initial data from REST fallback', async () => {
    mockedAxios.get.mockResolvedValueOnce({
      data: [
        {
          signal_id: '1',
          symbol: 'BTCUSDT',
          side: 'LONG',
          entry_price: 50000,
          tp1_price: 51000,
          tp2_price: 52000,
          tp3_price: 53000,
          sl_price: 49000,
          leverage: 2,
          confidence: 0.8,
          expected_net_profit_pct: 5,
          risk_profile: 'MEDIUM',
          timestamp: '2024-01-01T00:00:00Z'
        }
      ]
    })

    render(<Home />)

    await waitFor(() => expect(mockedAxios.get).toHaveBeenCalledTimes(1))

    expect(mockedAxios.get).toHaveBeenCalledWith('http://localhost:8000/api/v1/signals/live', {
      params: { risk_profile: 'medium' }
    })

    expect(await screen.findByText('BTCUSDT')).toBeInTheDocument()
  })

  it('updates signals when a WebSocket message is received', async () => {
    render(<Home />)

    expect(MockWebSocket.instances).toHaveLength(1)
    const socket = MockWebSocket.instances[0]

    await waitFor(() => expect(mockedAxios.get).toHaveBeenCalled())

    act(() => {
      socket.emit('message', {
        data: JSON.stringify([
          {
            signal_id: '2',
            symbol: 'ETHUSDT',
            side: 'SHORT',
            entry_price: 3000,
            tp1_price: 2900,
            tp2_price: 2800,
            tp3_price: 2700,
            sl_price: 3100,
            leverage: 3,
            confidence: 0.65,
            expected_net_profit_pct: 4.5,
            risk_profile: 'MEDIUM',
            timestamp: '2024-01-02T00:00:00Z'
          }
        ])
      })
    })

    expect(await screen.findByText('ETHUSDT')).toBeInTheDocument()
  })

  it('reconnects after the socket closes', async () => {
    render(<Home />)
    const socket = MockWebSocket.instances[0]

    await waitFor(() => expect(mockedAxios.get).toHaveBeenCalled())

    jest.useFakeTimers()

    act(() => {
      socket.emit('close', new Event('close'))
      jest.advanceTimersByTime(3000)
    })

    expect(MockWebSocket.instances.length).toBeGreaterThan(1)

    jest.useRealTimers()
  })
})
