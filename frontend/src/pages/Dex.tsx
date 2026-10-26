import { useEffect, useState } from "react";
import { api } from "../api";
import { Page, Stat } from "../ui";
const tone = (n: number) => (n >= 80 ? "text-emerald-600" : n >= 60 ? "text-amber-600" : "text-red-600");
export default function Dex() {
  const [devs, setDevs] = useState<any[]>([]); const [s, setS] = useState<any>(null); const [msg, setMsg] = useState("");
  const load = () => { api.get("/dex/devices").then((r) => setDevs(r.data)); api.get("/dex/summary").then((r) => setS(r.data)); };
  useEffect(() => { load(); }, []);
  const fix = async (id: number, action: string) => { const r = await api.post(`/dex/${id}/remediate`, null, { params: { action } }); setMsg(`${r.data.device.hostname}: ${action} → score ${r.data.before} → ${r.data.after}${r.data.ticket ? ` (ticket ${r.data.ticket})` : ""}`); load(); };
  return (
    <Page title="Digital Employee Experience (DEX)">
      {s && <div className="grid grid-cols-2 lg:grid-cols-4 gap-4"><Stat label="Devices monitored" value={s.devices} /><Stat label="Avg DEX score" value={s.avg_score} tone={tone(s.avg_score)} /><Stat label="Poor experience (<60)" value={s.poor} tone="text-red-600" /><Stat label="Issue types" value={Object.keys(s.issues).length} /></div>}
      {msg && <div className="text-sm text-emerald-700">{msg}</div>}
      <div className="card overflow-hidden"><table className="w-full"><thead><tr>{["Device", "User", "DEX", "Boot", "Crashes 7d", "CPU", "Mem", "Disk free", "Sentiment", "Detected issues → automated remediation"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
        <tbody>{devs.map((d) => <tr key={d.id}><td className="td font-mono text-xs">{d.hostname}<div className="text-slate-400">{d.os}</div></td><td className="td text-xs">{d.user}</td><td className={`td text-xl font-bold ${tone(d.score)}`}>{d.score}</td>
          <td className="td text-xs">{Math.round(d.boot_seconds)}s</td><td className="td text-xs">{d.crashes_7d}</td><td className="td text-xs">{Math.round(d.cpu_pct)}%</td><td className="td text-xs">{Math.round(d.mem_pct)}%</td><td className="td text-xs">{Math.round(d.disk_free_pct)}%</td><td className="td text-xs">{d.sentiment.toFixed(1)}/5</td>
          <td className="td">{d.issues.map((i: any) => <button key={i.issue} className="btn-ghost text-xs me-1 mb-1" onClick={() => fix(d.id, i.remediation)}>{i.issue} → {i.remediation.replace(/_/g, " ")}</button>)}{!d.issues.length && <span className="text-xs text-emerald-600">healthy</span>}</td></tr>)}</tbody></table></div>
    </Page>
  );
}
