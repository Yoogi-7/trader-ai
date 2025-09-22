
import useSWR from 'swr';

const fetcher = (url:string) => fetch(url).then(r=>r.json())

export default function Home(){
  const { data } = useSWR('http://localhost:8000/signals/live', fetcher, { refreshInterval: 5000 })
  return (
    <main style={{padding:20,fontFamily:'sans-serif'}}>
      <h1>Trader AI — Użytkownik</h1>
      <section>
        <h2>Live sygnały</h2>
        <pre>{JSON.stringify(data, null, 2)}</pre>
      </section>
      <section>
        <h2>Symulator (coming-up)</h2>
        <p>Symulacja od 100$ z ustawieniami kosztów.</p>
      </section>
    </main>
  )
}
