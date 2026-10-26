import { useEffect, useRef } from "react";
export type LiveEvent = { seq: number; module: string; id: number; number: string; event: string; by: string | null; by_id: number | null; fields: string[] };
const base = ((import.meta as any).env?.VITE_API_URL || "") + "/api";
/** Subscribe to live ticket updates (Server-Sent Events). Reconnects automatically. */
export function useLive(onEvent: (e: LiveEvent) => void) {
  const cb = useRef(onEvent); cb.current = onEvent;
  useEffect(() => {
    const tok = localStorage.getItem("nrsd_token"); if (!tok || typeof EventSource === "undefined") return;
    const es = new EventSource(`${base.replace(/\/$/, "")}/live/stream?token=${encodeURIComponent(tok)}`);
    es.onmessage = (m) => { try { cb.current(JSON.parse(m.data)); } catch { /* ignore */ } };
    return () => es.close();
  }, []);
}
