import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { authApi, clearTokens, setTokens, User } from '../api/client';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (access: string, refresh: string, user: User) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = async () => {
    try {
      const u = await authApi.me();
      setUser(u);
    } catch {
      setUser(null);
      clearTokens();
    }
  };

  useEffect(() => {
    refreshUser().finally(() => setLoading(false));
  }, []);

  const login = (access: string, refresh: string, u: User) => {
    setTokens(access, refresh);
    setUser(u);
  };

  const logout = async () => {
    try { await authApi.logout(); } catch { /* ignore */ }
    clearTokens();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth outside provider');
  return ctx;
}
