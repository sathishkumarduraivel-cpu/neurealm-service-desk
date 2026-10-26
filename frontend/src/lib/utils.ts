import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export const cn = (...i: ClassValue[]) => twMerge(clsx(i));
export const initials = (n?: string | null) => (n || "?").split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase();
export const humanize = (s?: string | null) => (s || "").replace(/_/g, " ");
const AV = ["bg-indigo-700", "bg-sky-700", "bg-emerald-700", "bg-amber-700", "bg-rose-700", "bg-violet-700", "bg-teal-700", "bg-fuchsia-700"];
export const avatarColor = (n?: string | null) => AV[[...(n || "")].reduce((a, c) => a + c.charCodeAt(0), 0) % AV.length];
export const relTime = (d?: string | null) => {
  if (!d) return "—"; const t = new Date(d + (/[zZ]|[+-]\d\d:?\d\d$/.test(d) ? "" : "Z")).getTime(); const s = (Date.now() - t) / 1000; const a = Math.abs(s);
  const f = (v: number, u: string) => `${Math.round(v)}${u}`; const r = a < 60 ? "just now" : a < 3600 ? f(a / 60, "m") : a < 86400 ? f(a / 3600, "h") : a < 2592000 ? f(a / 86400, "d") : f(a / 2592000, "mo");
  return r === "just now" ? r : s >= 0 ? `${r} ago` : `in ${r}`;
};
