import type { AppProps } from 'next/app';
import { WebSocketProvider } from '../src/ws';
import { AuthProvider } from '../src/context/AuthContext';
import '../styles/globals.css';

export default function MyApp({ Component, pageProps }: AppProps) {
  return (
    <AuthProvider>
      <WebSocketProvider>
        <Component {...pageProps} />
      </WebSocketProvider>
    </AuthProvider>
  );
}
