import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api, clearToken, getToken, onUnauthorized, setToken } from "../lib/api";

interface AuthContextValue {
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  startDemo: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => getToken() !== null);

  // An expired token still sits in localStorage and looks valid to the app until
  // a request fails. api.ts broadcasts that failure; here we act on it.
  useEffect(() => onUnauthorized(() => setIsAuthenticated(false)), []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password);
    setToken(res.access_token);
    setIsAuthenticated(true);
  }, []);

  const register = useCallback(async (email: string, password: string, fullName: string) => {
    const res = await api.register(email, password, fullName);
    setToken(res.access_token);
    setIsAuthenticated(true);
  }, []);

  const startDemo = useCallback(async () => {
    const res = await api.startDemo();
    setToken(res.access_token);
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setIsAuthenticated(false);
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthenticated, login, register, startDemo, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
