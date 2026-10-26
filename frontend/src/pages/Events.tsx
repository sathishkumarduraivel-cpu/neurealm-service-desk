import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Page, Stat, fmt } from "../ui";
const SC: Record<string, string> = { critical: "bg-red-600 text-white", major: "bg-orange-500 text-white", minor: "bg-amber-300", warning: "bg-yellow-100 text-yellow-800", info: "bg-slate-100" };
export default function Events() {
  const [rows, setRows] = useState<any[]>([]); const [st, setSt] = useState<any>(null); const [f, setF] = useState({ source: "prometheus", node: "vpn-gw-01", metric: "tunnel_down", severity: "critical", message: "IPsec tunnel down" });
  const load = () => { api.get("/events").then((r) => setRows(r.data)); api.get("/events/stats").then((r) => setSt(r.data)); };
  useEffect(() => { load(); }, []);
  const send = async () => { await api.post("/events", f); load(); };
  return (
    <Page title="Event Management">
      {st && <div className="grid grid-cols-2 lg:grid-cols-5 gap-4"><Stat label="Raw events" value={st.raw_events} /><Stat label="Alerts (deduplicated)" value={st.alerts} /><Stat label="Incidents created" value={st.incidents} />
        <Stat label="Noise reduction" value={`${st.noise_reduction_pct}%`} tone="text-emerald-600" /><Stat label="Open alerts" value={st.open} tone="text-red-600" /></div>}
      <div className="card p-4 flex flex-wrap gap-2 items-end"><div className="text-sm font-semibold w-full">Simulate event ingestion (Prometheus / Datadog / New Relic webhook)</div>
        {(["source", "node", "metric", "message"] as const).map((k) => <div key={k}><label className="label">{k}</label><input className="input" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></div>)}
        <div><label className="label">severity</label><select aria-label="severity" className="input" value={f.severity} onChange={(e) => setF({ ...f, severity: e.target.value })}>{["critical", "major", "minor", "warning", "info", "clear"].map((s) => <option key={s}>{s}</option>)}</select></div>
        <button className="btn" onClick={send}>Send event</button></div>
      <div className="card overflow-hidden"><table className="w-full"><thead><tr>{["Severity", "Node", "Metric", "Source", "Count", "State", "Incident", "Last seen"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
        <tbody>{rows.map((e) => <tr key={e.id}><td className="td"><span className={`px-2 py-0.5 rounded text-xs font-bold ${SC[e.severity]}`}>{e.severity}</span></td><td className="td">{e.node}</td><td className="td">{e.metric}<div className="text-xs text-slate-400">{e.message}</div></td>
          <td className="td">{e.source}</td><td className="td font-bold">×{e.count}</td><td className="td">{e.state}</td><td className="td">{e.incident_id ? <Link className="text-brand-600" to={`/incidents/${e.incident_id}`}>#{e.incident_id}</Link> : "—"}</td><td className="td text-xs">{fmt(e.last_seen)}</td></tr>)}
          {!rows.length && <tr><td colSpan={8} className="td text-center text-slate-400">No events yet — send one above.</td></tr>}</tbody></table></div>
    </Page>
  );
}
