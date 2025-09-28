import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import { api, fetcher } from '../api';

export type AuthUser = {
  id: number;
  email: string;
  role: 'ADMIN' | 'USER';
  risk_profile: string;
  capital: number;
};

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const TOKEN_KEY = 'auth_token';

function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadUser(currentToken: string | null) {
    if (!currentToken) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.me();
      setUser(me);
    } catch (error) {
      console.warn('auth me failed', error);
      window.localStorage.removeItem(TOKEN_KEY);
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const stored = getStoredToken();
    if (stored) {
      setToken(stored);
      setLoading(true);
      loadUser(stored);
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (email: string, password: string) => {
    const res = await api.login({ email, password });
    window.localStorage.setItem(TOKEN_KEY, res.access_token);
    setToken(res.access_token);
    setUser(res.user);
    setLoading(false);
    if (res.user.role === 'ADMIN') {
      router.replace('/admin');
    } else {
      router.replace('/');
    }
  };

  const logout = () => {
    window.localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    router.replace('/login');
  };

  const refresh = async () => {
    await loadUser(getStoredToken());
  };

  const value = useMemo(() => ({ user, token, loading, login, logout, refresh }), [user, token, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('AuthContext not available');
  return ctx;
}

export { getStoredToken };
