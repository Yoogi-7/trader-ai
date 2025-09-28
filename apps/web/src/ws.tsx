import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import { API_URL } from './api';

type WSMessage = any;

const WSContext = createContext<{ messages: WSMessage[], send: (s:string)=>void }>({ messages: [], send: ()=>{} });

export const WebSocketProvider: React.FC<{children: React.ReactNode}> = ({ children }) => {
  const [messages, setMessages] = useState<WSMessage[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const url = API_URL.replace(/^http/, 'ws') + '/ws/live';
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => ws.send('ping');
    ws.onmessage = (ev) => {
      try {
        if (ev.data === 'pong') return;
        const json = JSON.parse(ev.data);
        setMessages(m => [json, ...m].slice(0, 200));
      } catch { /* ignore */ }
    };
    ws.onclose = () => { wsRef.current = null; };
    return () => { ws.close(); };
  }, []);

  return (
    <WSContext.Provider value={{ messages, send: (s:string)=> wsRef.current?.send(s) }}>
      {children}
    </WSContext.Provider>
  );
};

export function useWS() {
  return useContext(WSContext);
}
