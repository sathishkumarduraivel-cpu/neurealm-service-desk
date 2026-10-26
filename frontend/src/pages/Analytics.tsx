import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BookMarked, Compass, Download, LayoutDashboard, Plus, Printer, Save, Trash2 } from "lucide-react";
import { api, errMsg } from "../api";
import { Page } from "../ui";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, NativeSelect } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/misc";
import { humanize } from "@/lib/utils";

const PAL = ["#1863DC", "#E5002B", "#F59E0B", "#081160", "#011C25", "#168AFF", "#FF8FA3"];
const MLAB: Record<string, string> = { count: "Count", open: "Still open", avg_age_hours: "Average age (hours)", breached_pct: "SLA breached (%)" };
const DEF = { module: "incident", rows: "priority", cols: null as string | null, metric: "count", days: 30, filter: {} as any, chart: "bar" };
type Spec = typeof DEF;

async function downloadCsv(url: string, body?: any) {
  try {
    const r = body ? await api.post(url, body, { responseType: "blob" }) : await api.get(url, { responseType: "blob" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(r.data); a.download = "servicedesk-report.csv"; a.click();
  } catch (x) { toast.error(errMsg(x)); }
}

export function Viz({ data, chart, height = 260 }: { data: any; chart: string; height?: number }) {
  if (!data) return null;
  if (!data.rows.length) return <p className="py-10 text-center text-sm text-muted-foreground">No records match. Try a longer date range.</p>;
  if (chart === "table" || data.matrix) return <PivotTable data={data} />;
  return <div style={{ height }}><ResponsiveContainer>{chart === "line" ? <LineChart data={data.rows}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="label" fontSize={11} /><YAxis fontSize={11} /><Tooltip /><Line dataKey="value" stroke={PAL[0]} strokeWidth={2} /></LineChart>
    : chart === "pie" ? <PieChart><Pie data={data.rows} dataKey="value" nameKey="label" outerRadius="80%" label={(e: any) => e.label}>{data.rows.map((_: any, i: number) => <Cell key={i} fill={PAL[i % PAL.length]} />)}</Pie><Tooltip /></PieChart>
    : <BarChart data={data.rows}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="label" fontSize={11} /><YAxis fontSize={11} /><Tooltip /><Bar dataKey="value" fill={PAL[0]} radius={[4, 4, 0, 0]} /></BarChart>}</ResponsiveContainer></div>;
}

function PivotTable({ data }: { data: any }) {
  if (!data.matrix) return <table className="w-full text-sm"><thead><tr><th className="th text-start">{humanize(data.spec.rows)}</th><th className="th text-end">{MLAB[data.spec.metric]}</th></tr></thead><tbody>{data.rows.map((r: any) => <tr key={r.label}><td className="td">{r.label}</td><td className="td text-end tabular-nums">{r.value}</td></tr>)}</tbody></table>;
  const max = Math.max(1, ...data.matrix.flatMap((m: any) => data.columns.map((c: string) => +m[c] || 0)));
  return <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr><th className="th text-start">{humanize(data.spec.rows)} \ {humanize(data.spec.cols)}</th>{data.columns.map((c: string) => <th key={c} className="th text-end">{c}</th>)}<th className="th text-end">Total</th></tr></thead>
    <tbody>{data.matrix.map((m: any) => <tr key={m.label}><td className="td font-medium">{m.label}</td>{data.columns.map((c: string) => <td key={c} className="td text-end tabular-nums" style={{ background: m[c] ? `rgba(130,34,142,${0.08 + 0.4 * (+m[c] / max)})` : undefined }}>{m[c] || "–"}</td>)}<td className="td text-end font-semibold tabular-nums">{m._total}</td></tr>)}</tbody></table></div>;
}

export function Explore() {
  const [qs] = useSearchParams(); const [meta, setMeta] = useState<any>(null);
  const [s, setS] = useState<Spec>(() => { try { return { ...DEF, ...JSON.parse(qs.get("spec") || "{}") }; } catch { return DEF; } });
  const [d, setD] = useState<any>(null); const [name, setName] = useState("");
  useEffect(() => { api.get("/analytics/meta").then((r) => setMeta(r.data)); }, []);
  useEffect(() => { api.post("/analytics/explore", s).then((r) => setD(r.data)).catch((x) => toast.error(errMsg(x))); }, [JSON.stringify(s)]);
  const set = (k: string, v: any) => setS({ ...s, [k]: v });
  const save = () => api.post("/analytics/reports", { name: name || `${humanize(s.module)} by ${humanize(s.rows)}`, spec: s }).then(() => { toast.success("Saved to the report library"); setName(""); }).catch((x) => toast.error(errMsg(x)));
  if (!meta) return null;
  const dimOpt = meta.dimensions.map((x: string) => <option key={x} value={x}>{humanize(x)}</option>);
  return (
    <Page title="Explore" icon={Compass} subtitle="Slice any module by up to two dimensions. Add a second dimension to get a pivot table." wide
      actions={<div className="flex gap-2 print:hidden"><Button variant="outline" onClick={() => downloadCsv("/analytics/explore.csv", s)}><Download />CSV</Button><Button variant="outline" onClick={() => window.print()}><Printer />Print</Button></div>}>
      <Card className="print:hidden"><CardContent className="grid grid-cols-2 gap-3 pt-5 md:grid-cols-4 lg:grid-cols-7">
        <div><Label>Module</Label><NativeSelect aria-label="Module" value={s.module} onChange={(e) => set("module", e.target.value)}>{meta.modules.map((m: any) => <option key={m.key} value={m.key}>{m.label}</option>)}</NativeSelect></div>
        <div><Label>Rows</Label><NativeSelect aria-label="Rows" value={s.rows} onChange={(e) => set("rows", e.target.value)}>{dimOpt}</NativeSelect></div>
        <div><Label>Columns (pivot)</Label><NativeSelect aria-label="Columns (pivot)" value={s.cols || ""} onChange={(e) => set("cols", e.target.value || null)}><option value="">None</option>{dimOpt}</NativeSelect></div>
        <div><Label>Measure</Label><NativeSelect aria-label="Measure" value={s.metric} onChange={(e) => set("metric", e.target.value)}>{meta.metrics.map((m: string) => <option key={m} value={m}>{MLAB[m]}</option>)}</NativeSelect></div>
        <div><Label>Period</Label><NativeSelect aria-label="Period" value={s.days} onChange={(e) => set("days", +e.target.value)}>{[7, 30, 90, 180, 365].map((n) => <option key={n} value={n}>Last {n} days</option>)}</NativeSelect></div>
        <div><Label>Chart</Label><NativeSelect aria-label="Chart" value={s.chart} onChange={(e) => set("chart", e.target.value)}>{["bar", "line", "pie", "table"].map((c) => <option key={c}>{c}</option>)}</NativeSelect></div>
        <div><Label>Only open</Label><NativeSelect aria-label="Only open" value={s.filter.open ? "1" : ""} onChange={(e) => set("filter", { ...s.filter, open: !!e.target.value })}><option value="">All</option><option value="1">Open only</option></NativeSelect></div>
      </CardContent></Card>
      <Card><CardHeader className="flex-row items-center justify-between"><CardTitle>{humanize(s.module)} by {humanize(s.rows)}{s.cols ? ` × ${humanize(s.cols)}` : ""} <Badge className="ms-2">{d?.total ?? 0} records</Badge></CardTitle>
        <div className="flex gap-2 print:hidden"><Input className="h-8 w-56" placeholder="Report name" value={name} onChange={(e) => setName(e.target.value)} /><Button size="sm" onClick={save}><Save />Save</Button></div></CardHeader>
        <CardContent><Viz data={d} chart={s.chart} height={320} /></CardContent></Card>
      {d?.records?.length > 0 && <Card className="print:hidden"><CardHeader><CardTitle>Records ({Math.min(200, d.total)} shown)</CardTitle></CardHeader><CardContent tabIndex={0} className="max-h-72 overflow-y-auto text-sm">{d.records.map((r: any) => <div key={r.id} className="flex gap-3 border-b py-1.5 last:border-0"><span className="w-24 font-mono text-xs text-muted-foreground">{r.number}</span><span className="flex-1">{r.title}</span><Badge>{humanize(r.state)}</Badge></div>)}</CardContent></Card>}
    </Page>
  );
}

const exploreLink = (spec: any) => `/analytics/explore?spec=${encodeURIComponent(JSON.stringify(spec))}`;
export function ReportLibrary() {
  const [t, setT] = useState<any[]>([]); const [r, setR] = useState<any[]>([]);
  const load = () => api.get("/analytics/reports").then((x) => setR(x.data));
  useEffect(() => { api.get("/analytics/templates").then((x) => setT(x.data)); load(); }, []);
  const del = (id: string) => api.delete(`/analytics/reports/${id}`).then(load).catch((x) => toast.error(errMsg(x)));
  return (
    <Page title="Report library" icon={BookMarked} subtitle="Start from a template or open a saved report. Saved reports can be added to boards.">
      <Card><CardHeader><CardTitle>Templates</CardTitle></CardHeader><CardContent className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{t.map((x) => <Link key={x.id} to={exploreLink(x.spec)} className="rounded-lg border p-3 text-sm hover:border-primary hover:bg-brand-50/40"><div className="font-medium">{x.name}</div><div className="text-xs text-muted-foreground">{humanize(x.spec.module)} · {x.spec.chart || "bar"}</div></Link>)}</CardContent></Card>
      <Card><CardHeader><CardTitle>Saved reports</CardTitle></CardHeader><CardContent>{r.length ? <table className="w-full text-sm"><thead><tr>{["Name", "Module", "Owner", ""].map((h) => <th key={h} className="th text-start">{h}</th>)}</tr></thead><tbody>{r.map((x) => <tr key={x.id}>
        <td className="td"><Link className="font-medium text-primary hover:underline" to={exploreLink(x.spec)}>{x.name}</Link></td><td className="td">{humanize(x.spec.module)}</td><td className="td">{x.owner_name}</td>
        <td className="td text-end"><Button size="sm" variant="ghost" onClick={() => downloadCsv(`/analytics/reports/${x.id}/csv`)}><Download />CSV</Button><Button size="sm" variant="ghost" aria-label={`Delete ${x.name}`} onClick={() => del(x.id)}><Trash2 /></Button></td></tr>)}</tbody></table>
        : <EmptyState icon={BookMarked} title="No saved reports yet" desc="Open Explore, build a view and press Save." />}</CardContent></Card>
    </Page>
  );
}

export function Boards() {
  const [b, setB] = useState<any[]>([]); const [name, setName] = useState(""); const nav = useNavigate();
  useEffect(() => { api.get("/analytics/boards").then((x) => setB(x.data)); }, []);
  const create = () => api.post("/analytics/boards", { name: name || "My board", widgets: [] }).then((x) => nav(`/analytics/boards/${x.data.id}`)).catch((x) => toast.error(errMsg(x)));
  return (
    <Page title="Boards" icon={LayoutDashboard} subtitle="Dashboards built from saved reports. Share them with your team or keep them to yourself."
      actions={<div className="flex gap-2"><Input className="w-48" placeholder="New board name" value={name} onChange={(e) => setName(e.target.value)} /><Button onClick={create}><Plus />Create</Button></div>}>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{b.map((x) => <Link key={x.id} to={`/analytics/boards/${x.id}`}><Card className="h-full hover:border-primary"><CardContent className="pt-5"><div className="font-semibold">{x.name}</div><div className="text-xs text-muted-foreground">{x.widgets.length} widgets · by {x.owner_name}{x.shared ? " · shared" : ""}</div></CardContent></Card></Link>)}</div>
      {!b.length && <EmptyState icon={LayoutDashboard} title="No boards yet" desc="Create one and add saved reports to it." />}
    </Page>
  );
}

export function BoardView() {
  const { id } = useParams(); const [b, setB] = useState<any>(null); const [lib, setLib] = useState<any[]>([]); const [add, setAdd] = useState("");
  const load = () => api.get(`/analytics/boards/${id}`).then((x) => setB(x.data)).catch((x) => toast.error(errMsg(x)));
  useEffect(() => { load(); api.get("/analytics/reports").then((x) => setLib(x.data)); }, [id]);
  const save = (widgets: any[]) => api.put(`/analytics/boards/${id}`, { name: b.name, shared: b.shared, widgets: widgets.map((w) => ({ report: w.report.id ?? w.report, size: w.size })) }).then(load).catch((x) => toast.error(errMsg(x)));
  if (!b) return null;
  return (
    <Page title={b.name} icon={LayoutDashboard} subtitle={`Board by ${b.owner_name}`} wide
      actions={<div className="flex gap-2 print:hidden"><NativeSelect aria-label="Add a report" value={add} onChange={(e) => setAdd(e.target.value)}><option value="">Add a saved report…</option>{lib.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</NativeSelect>
        <Button disabled={!add} onClick={() => { save([...b.widgets, { report: add, size: "half" }]); setAdd(""); }}><Plus />Add</Button><Button variant="outline" onClick={() => window.print()}><Printer />Print</Button></div>}>
      <div className="grid gap-4 lg:grid-cols-2">{b.widgets.map((w: any, i: number) => <Card key={i} className={w.size === "full" ? "lg:col-span-2" : ""}>
        <CardHeader className="flex-row items-center justify-between"><CardTitle className="text-sm">{w.report.name}</CardTitle><div className="flex gap-1 print:hidden">
          <Button size="sm" variant="ghost" onClick={() => save(b.widgets.map((x: any, k: number) => k === i ? { ...x, size: x.size === "full" ? "half" : "full" } : x))}>{w.size === "full" ? "Narrow" : "Wide"}</Button>
          <Button size="sm" variant="ghost" asChild><Link to={exploreLink(w.report.spec)}>Open</Link></Button>
          <Button size="sm" variant="ghost" aria-label="Remove widget" onClick={() => save(b.widgets.filter((_: any, k: number) => k !== i))}><Trash2 /></Button></div></CardHeader>
        <CardContent><Viz data={w.data} chart={w.report.spec.chart} height={220} /></CardContent></Card>)}</div>
      {!b.widgets.length && <EmptyState icon={LayoutDashboard} title="This board is empty" desc="Add a saved report from the menu above." />}
    </Page>
  );
}
