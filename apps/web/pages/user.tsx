import { useEffect, useState, useRef } from 'react'

type Signal = {
  id:number; symbol:string; dir:string; entry:number; sl:number; tp:number[];
  lev:number; risk:number; margin_mode:string; expected_net_pct:number; confidence:number;
  status:string; reason_discard?:string; ts?:number; source?:string;
}

export default function User(){
  const [signals,setSignals]=useState<Signal[]>([])
  const [capital,setCapital]=useState(100)
  const [risk,setRisk]=useState('LOW')
  const [pairs,setPairs]=useState('BTCUSDT,ETHUSDT')
  const wsRef = useRef<WebSocket | null>(null)

  const generate=async()=>{
    const r=await fetch('http://localhost:8000/signals/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pairs:pairs.split(','),risk_profile:risk,capital})})
    const j=await r.json(); setSignals(prev=>[...j,...prev].slice(0,200))
  }

  const saveProfile=async()=>{
    await fetch(`http://localhost:8000/settings/profile?risk_profile=${risk}`,{method:'POST'})
    await fetch(`http://localhost:8000/capital?capital=${capital}`,{method:'POST'})
  }

  useEffect(()=>{
    const ws = new WebSocket('ws://localhost:8000/ws/live')
    ws.onmessage = (ev)=>{
      try{
        const msg = JSON.parse(ev.data)
        if(msg.channel==='signals'){
          const s = msg.payload as Signal
          setSignals(prev=>[s, ...prev].slice(0,200))
        }
      }catch(e){ /* ignore */ }
    }
    wsRef.current = ws
    return ()=>{ ws.close() }
  },[])

  return (<main style={{padding:20}}>
    <h2>Użytkownik (Live)</h2>
    <div style={{display:'flex',gap:10,alignItems:'center'}}>
      <label>Kapitał: </label><input type="number" value={capital} onChange={e=>setCapital(parseFloat(e.target.value))}/>
      <label>Ryzyko: </label>
      <select value={risk} onChange={e=>setRisk(e.target.value)}>
        <option>LOW</option><option>MED</option><option>HIGH</option>
      </select>
      <label>Pary: </label>
      <input value={pairs} onChange={e=>setPairs(e.target.value)}/>
      <button onClick={generate}>Generuj sygnały (HTTP)</button>
      <button onClick={saveProfile}>Zapisz profil</button>
    </div>
    <p style={{marginTop:10,opacity:0.7}}>WebSocket: odbiera sygnały generowane przez worker/ML w tle.</p>
    <table style={{marginTop:20, width:'100%'}}>
      <thead><tr><th>ID</th><th>Źródło</th><th>Symbol</th><th>Kier.</th><th>Entry</th><th>TP</th><th>SL</th><th>Net %</th><th>Conf.</th><th>Status</th></tr></thead>
      <tbody>{signals.map(s=>(<tr key={`${s.source}-${s.id}`}>
        <td>{s.id}</td><td>{s.source}</td><td>{s.symbol}</td><td>{s.dir}</td>
        <td>{s.entry}</td><td>{s.tp?.join(',')}</td><td>{s.sl}</td>
        <td>{s.expected_net_pct}</td><td>{s.confidence}</td><td>{s.status}</td>
      </tr>))}</tbody>
    </table>
  </main>)
}
