import type { AppProps } from 'next/app';
import { WebSocketProvider } from '../src/ws';
import '../styles/globals.css';

export default function MyApp({ Component, pageProps }: AppProps) {
  return (
    <WebSocketProvider>
      <Component {...pageProps} />
    </WebSocketProvider>
  );
}
