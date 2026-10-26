import { createContext, useContext, useState, type ReactNode } from "react";
import { api, type User } from "./api";
export type LoginResult = { user: User } | { mfa_token: string };
type Ctx = {
  user: User | null; impersonating: boolean;
  login: (e: string, p: string) => Promise<LoginResult>;
  verifyMfa: (mfa_token: string, code: string) => Promise<User>;
  register: (full_name: string, email: string, password: string) => Promise<User>;
  impersonate: (id: number) => Promise<User>; stopImpersonating: () => Promise<User>;
  logout: () => void;
};
const C = createContext<Ctx>(null as any);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => JSON.parse(localStorage.getItem("nrsd_user") || "null"));
  const [impersonating, setImp] = useState(() => !!localStorage.getItem("nrsd_imp"));
  const accept = (data: any) => {
    localStorage.setItem("nrsd_token", data.access_token); localStorage.setItem("nrsd_user", JSON.stringify(data.user));
    if (data.impersonator) localStorage.setItem("nrsd_imp", String(data.impersonator)); else localStorage.removeItem("nrsd_imp");
    setImp(!!data.impersonator); setUser(data.user); return data.user as User;
  };
  const login = async (email: string, password: string): Promise<LoginResult> => {
    const { data } = await api.post("/auth/login", { email, password });
    if (data.mfa_required) return { mfa_token: data.mfa_token };
    return { user: accept(data) };
  };
  const verifyMfa = async (mfa_token: string, code: string) => accept((await api.post("/auth/mfa", { mfa_token, code })).data);
  const register = async (full_name: string, email: string, password: string) => accept((await api.post("/auth/register", { full_name, email, password })).data);
  const impersonate = async (id: number) => accept((await api.post(`/admin/impersonate/${id}`)).data);
  const stopImpersonating = async () => accept((await api.post("/admin/impersonate/stop")).data);
  const logout = () => { ["nrsd_token", "nrsd_user", "nrsd_imp"].forEach((k) => localStorage.removeItem(k)); setImp(false); setUser(null); };
  return <C.Provider value={{ user, impersonating, login, verifyMfa, register, impersonate, stopImpersonating, logout }}>{children}</C.Provider>;
}
export const useAuth = () => useContext(C);
export const isStaff = (u: User | null) => !!u && u.role !== "end_user";
