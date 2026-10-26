import { ChartTooltip, axis, grid } from "@/components/charts";
import { useEffect, useState } from "react";
import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link } from "react-router-dom";
import { api, errMsg } from "../api";
import { pathFor } from "../modules";
import { Page, Stat, Ico, PageLoading } from "../ui";
// No monetary values in Neurealm Service Desk: recommendations are ranked by impact (high / medium / low).
const IMP: Record<string, string> = { high: "text-red-600", medium: "text-amber-600", low: "text-slate-500" };
const COL = ["#6366f1", "#0ea5e9", "#10b981", "#f97316", "#8b5cf6"];
const TC: Record<string, string> = { rightsizing: "bg-sky-100 text-sky-700", saas_harvest: "bg-violet-100 text-violet-700", license_reclaim: "bg-emerald-100 text-emerald-700", anomaly: "bg-red-100 text-red-700", compliance: "bg-amber-100 text-amber-700" };
export default function FinOps() {
  const [c, setC] = useState<any>(null); const [msg, setMsg] = useState<any>(null);
  const load = () => api.get("/finops/center").then((r) => setC(r.data));
  useEffect(() => { load(); }, []);
  const apply = async (id: string) => { try { const r = await api.post("/finops/apply", null, { params: { rec_id: id } }); setMsg(r.data.record); load(); } catch (x) { setMsg({ title: errMsg(x) }); } };
  if (!c) return <Page title="Optimisation Center"><PageLoading /></Page>;
  return (
    <Page title="Optimisation Center" subtitle="Ideas to use cloud and SaaS more efficiently, ranked by impact. No prices are shown.">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4"><Stat label={`Usage index ${c.current_month}`} value={c.current_index} /><Stat label="Open ideas" value={c.open_count} /><Stat label="High impact" value={c.high_impact_open} tone="text-red-600" /><Stat label="Actioned" value={c.applied_count} tone="text-emerald-600" /></div>
      {msg && <div className="text-sm text-emerald-700">{msg.number ? <>Created <Link className="underline" to={`${pathFor(msg.module)}/${msg.id}`}>{msg.number}</Link> — {msg.title}</> : msg.title}</div>}
      <div className="card p-4"><h3 className="font-semibold mb-2">Unified usage (cloud + SaaS)</h3><ResponsiveContainer width="100%" height={240}><AreaChart data={c.trend}><CartesianGrid {...grid} /><XAxis {...axis} dataKey="month" /><YAxis {...axis} /><Tooltip content={<ChartTooltip formatter={(v: any) => `${v}`} />} cursor={{ fill: "hsl(var(--muted))" }} /><Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
        {c.providers.map((p: string, i: number) => <Area key={p} dataKey={p} stackId="1" stroke={COL[i % 5]} fill={COL[i % 5]} fillOpacity={0.5} />)}</AreaChart></ResponsiveContainer></div>
      <div className="card overflow-hidden"><div className="px-4 py-3 font-semibold"><Ico n="sparkles" className="me-1.5 text-indigo-500" />Optimisation ideas</div><table className="w-full"><thead><tr>{["Type", "Recommendation", "Impact", ""].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
        <tbody>{c.recommendations.map((r: any) => <tr key={r.id}><td className="td"><span className={`px-2 py-0.5 rounded text-xs ${TC[r.type]}`}>{r.type.replace("_", " ")}</span></td><td className="td">{r.title}</td><td className={`td font-semibold capitalize ${IMP[r.impact]}`}>{r.impact}</td>
          <td className="td">{r.applied ? <span className="text-xs text-emerald-600"><Ico n="check" className="me-1" />Actioned</span> : <button className="btn text-xs" onClick={() => apply(r.id)}>Action → {r.action}</button>}</td></tr>)}</tbody></table></div>
    </Page>
  );
}
