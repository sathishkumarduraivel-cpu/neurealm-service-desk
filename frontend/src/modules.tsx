import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import { useAuth } from "./auth";
export type Field = { name: string; label: string; type: string; options?: string[] };
export type ModuleMeta = { key: string; label: string; prefix: string; section: string; fields: Field[]; custom_page?: string; hidden?: boolean; create: string[]; states: string[]; ai: boolean; sla: boolean };
const C = createContext<Record<string, ModuleMeta>>({});
export function ModulesProvider({ children }: { children: ReactNode }) {
  const [m, setM] = useState<Record<string, ModuleMeta>>({}); const { user } = useAuth();
  useEffect(() => { if (user && localStorage.getItem("nrsd_token")) api.get("/meta/modules").then((r) => setM(Object.fromEntries(r.data.map((x: ModuleMeta) => [x.key, x])))).catch(() => {}); }, [user?.id]);
  return <C.Provider value={m}>{children}</C.Provider>;
}
export const useModules = () => useContext(C);
const CORE: Record<string, string> = { incident: "/incidents", problem: "/problems", change: "/changes", request: "/requests" };
export const pathFor = (m: string) => CORE[m] || `/m/${m}`;
