import { brandify } from "@/brand";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import en from "./locales/en.json"; import hi from "./locales/hi.json"; import es from "./locales/es.json"; import fr from "./locales/fr.json";
import de from "./locales/de.json"; import ja from "./locales/ja.json"; import ar from "./locales/ar.json";
export const LANGUAGES = [
  { code: "en", name: "English", dir: "ltr" }, { code: "hi", name: "हिन्दी", dir: "ltr" }, { code: "es", name: "Español", dir: "ltr" },
  { code: "fr", name: "Français", dir: "ltr" }, { code: "de", name: "Deutsch", dir: "ltr" }, { code: "ja", name: "日本語", dir: "ltr" }, { code: "ar", name: "العربية", dir: "rtl" },
] as const;
const DICTS: Record<string, Record<string, string>> = { en, hi, es, fr, de, ja, ar };
type Ctx = { lang: string; setLang: (l: string) => void; t: (s: string, vars?: Record<string, string | number>) => string };
const C = createContext<Ctx>({ lang: "en", setLang: () => {}, t: (s) => s });
/** Keys are the English strings themselves, so a missing translation simply falls back to English. */
const LC: Record<string, Record<string, string>> = {};
/** Case-insensitive fallback so "in progress" and "In Progress" both translate. */
const lower = (lang: string) => (LC[lang] ||= Object.fromEntries(Object.entries(DICTS[lang] || {}).map(([k, v]) => [k.toLowerCase(), v])));
export function translate(lang: string, s: string, vars?: Record<string, string | number>) {
  const d = DICTS[lang]; let out = d?.[s] || lower(lang)[s.toLowerCase()] || DICTS.en[s] || s;
  if (vars) for (const [k, v] of Object.entries(vars)) out = out.replace(`{${k}}`, String(v));
  return brandify(out);
}
export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState(() => localStorage.getItem("nrsd_lang") || "en");
  useEffect(() => { const m = LANGUAGES.find((l) => l.code === lang) || LANGUAGES[0]; document.documentElement.lang = m.code; document.documentElement.dir = m.dir; localStorage.setItem("nrsd_lang", m.code); }, [lang]);
  return <C.Provider value={{ lang, setLang, t: (s, v) => translate(lang, s, v) }}>{children}</C.Provider>;
}
export const useT = () => useContext(C);
