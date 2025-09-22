
import { useEffect, useState } from 'react'

export default function Home() {
  const [heartbeat, setHeartbeat] = useState<any>(null)
  const [signals, setSignals] = useState<any[]>([])

  useEffect(() => {
    const ws = new WebSocket(`ws://${typeof window !== 'undefined' ? window.location.hostname : 'localhost'}:8000/ws/live`)
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data)
        if (data.type === 'heartbeat') setHeartbeat(data)
      } catch {}
    }
    return () => ws.close()
  }, [])

  return (
    <main style={{ padding: 24, fontFamily: 'sans-serif' }}>
      <h1>Trader AI — User Panel</h1>
      <p>Live heartbeat: {heartbeat ? `${heartbeat.t} @ ${new Date(heartbeat.ts*1000).toLocaleTimeString()}` : '—'}</p>
      <section style={{ marginTop: 24 }}>
        <h2>Controls</h2>
        <p>Ustaw profil ryzyka i kapitał w API, potem uruchom backtest.</p>
      </section>
    </main>
  )
}
