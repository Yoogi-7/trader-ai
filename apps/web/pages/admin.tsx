import useSWR from 'swr'
const fetcher=(u:string)=>fetch(u).then(r=>r.json())

export default function Admin(){
  const {data:bf}=useSWR('http://localhost:8000/backfill/status',fetcher,{refreshInterval:2000})
  const {data:tr}=useSWR('http://localhost:8000/train/status',fetcher,{refreshInterval:3000})
  const {data:bt}=useSWR('http://localhost:8000/backtest/results',fetcher,{refreshInterval:5000})

  return (<main style={{padding:20}}>
    <h2>Admin</h2>
    <h3>Backfill</h3>
    <pre>{JSON.stringify(bf,null,2)}</pre>
    <h3>Trening</h3>
    <pre>{JSON.stringify(tr,null,2)}</pre>
    <h3>Backtesty</h3>
    <pre>{JSON.stringify(bt,null,2)}</pre>
  </main>)
}