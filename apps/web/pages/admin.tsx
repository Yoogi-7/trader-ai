
import useSWR from 'swr';
const fetcher = (url:string) => fetch(url).then(r=>r.json())

export default function Admin(){
  const { data: train } = useSWR('http://localhost:8000/train/status', fetcher, { refreshInterval: 3000 })
  const { data: backfill } = useSWR('http://localhost:8000/backfill/status', fetcher, { refreshInterval: 3000 })
  return (
    <main style={{padding:20,fontFamily:'sans-serif'}}>
      <h1>Trader AI — Admin</h1>
      <section>
        <h2>Backfill</h2>
        <pre>{JSON.stringify(backfill, null, 2)}</pre>
      </section>
      <section>
        <h2>Training</h2>
        <pre>{JSON.stringify(train, null, 2)}</pre>
      </section>
      <section>
        <h2>Model registry &amp; metryki</h2>
        <p>OOS hit-rate, PF, MAR...</p>
      </section>
    </main>
  )
}
