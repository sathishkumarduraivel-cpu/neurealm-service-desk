import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "@/api";
import { useAuth } from "@/auth";
type F = Record<string, boolean>;
const C = createContext<{ features: F; enabled: (k?: string) => boolean; save: (f: F) => Promise<void> }>({ features: {}, enabled: () => true, save: async () => {} });
export function FeaturesProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth(); const [features, setF] = useState<F>({});
  useEffect(() => { if (user) api.get("/features").then((r) => setF(r.data)).catch(() => {}); }, [user]);
  const save = useCallback(async (f: F) => { const r = await api.put("/features", f); setF(r.data); }, []);
  return <C.Provider value={{ features, enabled: (k) => !k || !!features[k], save }}>{children}</C.Provider>;
}
export const useFeatures = () => useContext(C);
