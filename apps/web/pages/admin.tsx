import useSWR from 'swr'
import { useEffect, useRef, useState } from 'react'
const fetcher=(u:string)=>fetch(u).then(r=>r.json())

type LiveMsg = { channel:string; payload:any }
type Progress = { symbol:string; tf:string; pct:number; processed:number; last_ts:number; speed_cpm:number; eta_sec:number; error?:string }

export default function Admin(){
  const {data:bf}=useSWR('http://localhost:8000/backfill/status',fetcher,{refreshInterval:5000})
  const {data:tr}=useSWR('http://localhost:8000/train/status',fetcher,{refreshInterval:8000})
  const {data:bt}=useSWR('http://localhost:8000/backtest/results',fetcher,{refreshInterval:8000})
  const {data:pos}=useSWR('http://localhost:8000/positions/open',fetcher,{refreshInterval:5000})
  const [live,setLive]=useState<LiveMsg[]>([])
  const [progress,setProgress]=useState<Record<string,Progress>>({})
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(()=>{
    const ws = new WebSocket('ws://localhost:8000/ws/live')
    ws.onmessage = (ev)=>{
      try{
        const msg = JSON.parse(ev.data) as LiveMsg
        if(msg.channel==='progress'){
          const p = msg.payload as Progress
          const key = `${p.symbol}-${p.tf}`
          setProgress(prev=>({...prev,[key]:p}))
        }
        setLive(prev=>[msg,...prev].slice(0,200))
      }catch(e){}
    }
    wsRef.current = ws
    return ()=>{ ws.close() }
  },[])

  const renderProgress=()=>{
    const keys = Object.keys(progress)
    if(keys.length===0) return <p>Brak aktywnych zadań backfill.</p>
    return keys.map(k=>{
      const p = progress[k]
      const err = p.error
      const pct = p.pct<0?0:p.pct
      return (
        <div key={k} style={{marginBottom:12}}>
          <div style={{display:'flex',justifyContent:'space-between'}}>
            <strong>{p.symbol} {p.tf}</strong>
            <span>{pct.toFixed(2)}%</span>
          </div>
          <div style={{background:'#eee',borderRadius:6,overflow:'hidden'}}>
            <div style={{width:`${pct}%`,height:10,background: err?'#e74c3c':'#2ecc71',transition:'width .2s'}}/>
          </div>
          <small>Świece: {p.processed} • Szybkość: {p.speed_cpm} cpm • ETA: {Math.max(0,p.eta_sec)} s • last_ts: {p.last_ts}</small>
          {err && <div style={{color:'#e74c3c'}}>Błąd: {err}</div>}
        </div>
      )
    })
  }

  return (<main style={{padding:20}}>
    <h2>Admin</h2>
    <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:20}}>
      <section>
        <h3>Backfill – status (REST)</h3>
        <pre>{JSON.stringify(bf,null,2)}</pre>
        <h3>Trening (REST)</h3>
        <pre>{JSON.stringify(tr,null,2)}</pre>
        <h3>Backtesty (REST)</h3>
        <pre>{JSON.stringify(bt,null,2)}</pre>
        <h3>Pozycje (paper)</h3>
        <pre>{JSON.stringify(pos,null,2)}</pre>
      </section>
      <section>
        <h3>Backfill – progress (WebSocket)</h3>
        {renderProgress()}
        <h3>Live (surowe eventy)</h3>
        <ul>
          {live.map((m,i)=>(
            <li key={i}><code>{m.channel}</code> → <small>{new Date().toLocaleTimeString()}</small>
              <pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(m.payload)}</pre>
            </li>
          ))}
        </ul>
      </section>
    </div>
  </main>)
}
