import type { ReactNode } from "react";
// Neurealm Service Desk is light-only (Neurealm brand). Kept as a tiny shim so existing imports keep working.
export function ThemeProvider({ children }: { children: ReactNode }) { document.documentElement.classList.remove("dark"); return <>{children}</>; }
export const useTheme = () => ({ theme: "light" as const, toggle: () => {}, set: (_: "light") => {} });
