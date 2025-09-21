import { useEffect, useState } from 'react'

export default function User(){
  const [signals,setSignals]=useState<any[]>([])
  const [capital,setCapital]=useState(100)
  const [risk,setRisk]=useState('LOW')
  const [pairs,setPairs]=useState('BTCUSDT,ETHUSDT')

  const generate=async()=>{
    const r=await fetch('http://localhost:8000/signals/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pairs:pairs.split(','),risk_profile:risk,capital})})
    setSignals(await r.json())
  }

  return (<main style={{padding:20}}>
    <h2>Użytkownik</h2>
    <div>
      <label>Kapitał: </label><input type="number" value={capital} onChange={e=>setCapital(parseFloat(e.target.value))}/>
      <label style={{marginLeft:10}}>Ryzyko: </label>
      <select value={risk} onChange={e=>setRisk(e.target.value)}>
        <option>LOW</option><option>MED</option><option>HIGH</option>
      </select>
      <label style={{marginLeft:10}}>Pary: </label>
      <input value={pairs} onChange={e=>setPairs(e.target.value)}/>
      <button onClick={generate} style={{marginLeft:10}}>Generuj sygnały</button>
    </div>
    <table style={{marginTop:20}}>
      <thead><tr><th>ID</th><th>Symbol</th><th>Kier.</th><th>Entry</th><th>TP</th><th>SL</th><th>Net %</th><th>Status</th></tr></thead>
      <tbody>{signals.map(s=>(<tr key={s.id}><td>{s.id}</td><td>{s.symbol}</td><td>{s.dir}</td><td>{s.entry}</td><td>{s.tp.join(',')}</td><td>{s.sl}</td><td>{s.expected_net_pct}</td><td>{s.status}</td></tr>))}</tbody>
    </table>
  </main>)
}