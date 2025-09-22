"use client";
import { useEffect, useState } from "react";

export default function LiveSignals(){
  const [msgs, setMsgs] = useState<string[]>([]);
  useEffect(()=>{
    const ws = new WebSocket("ws://localhost:8000/ws/live");
    ws.onmessage = (ev)=> setMsgs(m=>[ev.data,...m].slice(0,50));
    return ()=> ws.close();
  },[]);
  return (
    <div className="p-4 bg-white rounded-2xl shadow">
      <h2 className="font-semibold mb-2">Live sygnały</h2>
      <div className="text-sm space-y-1 max-h-64 overflow-auto">
        {msgs.map((m,i)=><pre key={i} className="bg-slate-100 p-2 rounded">{m}</pre>)}
      </div>
    </div>
  );
}
