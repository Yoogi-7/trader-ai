import useSWR from 'swr';

const api = (path: string) => `http://localhost:8000${path}`;
const fetcher = (url:string) => fetch(url).then(r=>r.json());

export default function Admin(){
  const { data, mutate } = useSWR(api('/backfill/status'), fetcher, { refreshInterval: 3000 });

  const act = async (url: string, body: any) => {
    await fetch(api(url), { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
    mutate();
  };

  return (
    <main style={{padding:20,fontFamily:'Inter, system-ui, sans-serif', maxWidth: 1000, margin: '0 auto'}}>
      <h1 style={{fontSize:28, fontWeight:700, marginBottom:12}}>Trader AI — Admin</h1>

      <section style={{marginTop:20}}>
        <h2 style={{fontSize:20, fontWeight:600}}>Backfill — status</h2>
        <p>Odświeża się co 3 sekundy. Widzisz postęp, ETA, luki i akcje sterujące (pause/resume/restart).</p>
        <div style={{display:'grid', gap:12, marginTop:12}}>
          {(data?.items || []).map((row:any) => (
            <div key={`${row.symbol}-${row.tf}`} style={{border:'1px solid #eee', borderRadius:12, padding:12}}>
              <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                <div>
                  <strong>{row.symbol}</strong> <span style={{opacity:0.6}}>{row.tf}</span>
                  <div style={{fontSize:12, opacity:0.8}}>Status: {row.status} | Progress: {row.progress_pct ?? '—'}% ({row.done ?? '—'}/{row.total ?? '—'})</div>
                </div>
                <div style={{display:'flex', gap:8}}>
                  <button onClick={()=>act('/backfill/pause', {symbol: row.symbol, tf: row.tf})}>Pause</button>
                  <button onClick={()=>act('/backfill/resume', {symbol: row.symbol, tf: row.tf})}>Resume</button>
                  <button onClick={()=>act('/backfill/restart', {symbol: row.symbol, tf: row.tf})}>Restart chunk</button>
                </div>
              </div>
              <div style={{height:8, background:'#f3f4f6', borderRadius:8, marginTop:8, overflow:'hidden'}}>
                <div style={{width:`${row.progress_pct||0}%`, height:'100%', background:'#10b981', transition:'width .5s'}} />
              </div>
              {(row.gaps?.length>0) && (
                <details style={{marginTop:8}}>
                  <summary>Luki ({row.gaps.length})</summary>
                  <pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(row.gaps, null, 2)}</pre>
                </details>
              )}
              <div style={{fontSize:12, opacity:0.7, marginTop:6}}>Updated: {row.updated_at || '—'}</div>
            </div>
          ))}
        </div>
      </section>
    </main>
  )
}
