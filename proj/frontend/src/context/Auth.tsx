import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { auth } from "../services"; import { tokenStore } from "../services/api";
const Ctx = createContext<any>(null); export const useAuth = () => useContext(Ctx);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<any>(null); const [loading, setLoading] = useState(!!tokenStore.get()); const qc = useQueryClient();
  useEffect(() => { if (tokenStore.get()) auth.me().then(setUser).catch(() => tokenStore.clear()).finally(() => setLoading(false)); }, []);
  useEffect(() => { const h = () => { setUser(null); qc.clear(); }; window.addEventListener("auth:expired", h); return () => window.removeEventListener("auth:expired", h); }, []);
  const login = async (e: string, p: string) => { const r = await auth.login(e, p); tokenStore.set(r.access_token); setUser(r.user); };
  const logout = () => { tokenStore.clear(); setUser(null); qc.clear(); };
  return <Ctx.Provider value={{ user, loading, login, logout }}>{children}</Ctx.Provider>;
}
