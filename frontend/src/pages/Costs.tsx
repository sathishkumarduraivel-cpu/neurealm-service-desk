import { ChartTooltip, axis, grid } from "@/components/charts";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { Page, Stat, Ico, PageLoading } from "../ui";
// No monetary values in Neurealm Service Desk: usage is a relative index (first month = 100) and shares are percentages.
const COL = ["#6366f1", "#0ea5e9", "#10b981", "#f97316", "#8b5cf6"];
export default function Costs() {
  const [c, setC] = useState<any>(null);
  useEffect(() => { api.get("/costs").then((r) => setC(r.data)); }, []);
  if (!c) return <Page title="Cloud & SaaS Usage"><PageLoading /></Page>;
  return (
    <Page title="Cloud & SaaS Usage" subtitle="Usage index: the first month is 100. No prices are shown.">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4"><Stat label={`Usage index ${c.current_month}`} value={c.current_index} />{c.by_kind.map((k: any) => <Stat key={k.name} label={`${k.name} share`} value={`${k.share_pct}%`} />)}<Stat label="Anomalies" value={c.anomalies.length} tone="text-red-600" /></div>
      <div className="card p-4"><h3 className="font-semibold mb-2">Monthly usage by provider</h3><ResponsiveContainer width="100%" height={280}><BarChart data={c.trend}><CartesianGrid {...grid} /><XAxis {...axis} dataKey="month" /><YAxis {...axis} /><Tooltip content={<ChartTooltip formatter={(v: any) => `${v}`} />} cursor={{ fill: "hsl(var(--muted))" }} /><Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
        {c.providers.map((p: string, i: number) => <Bar key={p} dataKey={p} stackId="a" fill={COL[i % COL.length]} />)}</BarChart></ResponsiveContainer></div>
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="card p-4"><h3 className="font-semibold mb-2"><Ico n="flag" className="me-1.5 text-red-500" />Usage anomalies (vs. trailing baseline)</h3>{c.anomalies.map((a: any) => <div key={a.service} className="flex justify-between text-sm py-1 border-b last:border-0"><span>{a.provider} · {a.service}</span><span><b className="text-red-600">+{a.increase_pct}%</b> <span className="text-xs text-slate-400">vs. baseline</span></span></div>)}</div>
        <div className="card overflow-hidden"><table className="w-full"><thead><tr>{["Provider", "Service", "Share of usage", "Utilization"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody>{c.services.sort((a: any, b: any) => b.share_pct - a.share_pct).map((s: any) => <tr key={s.provider + s.service}><td className="td">{s.provider}</td><td className="td">{s.service}</td><td className="td">{s.share_pct}%</td><td className={`td ${s.utilization < 0.4 ? "text-red-600 font-bold" : ""}`}>{Math.round(s.utilization * 100)}%</td></tr>)}</tbody></table></div>
      </div>
    </Page>
  );
}
