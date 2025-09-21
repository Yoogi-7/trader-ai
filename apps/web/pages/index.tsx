import Link from 'next/link'
export default function Home(){
  return (<main style={{padding:20}}>
    <h1>Trader AI</h1>
    <ul>
      <li><Link href="/user">Panel użytkownika</Link></li>
      <li><Link href="/admin">Panel admina</Link></li>
    </ul>
  </main>)
}