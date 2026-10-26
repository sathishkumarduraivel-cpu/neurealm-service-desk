import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { CalendarDays, KanbanSquare, Plus, RefreshCcw, Siren, Snowflake, Trash2, Users } from "lucide-react";
import { api, errMsg } from "../api";
import { useAuth } from "../auth";
import { Page, fmt } from "../ui";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { EmptyState, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/misc";
import { humanize } from "@/lib/utils";

const RISK: Record<string, any> = { high: "red", moderate: "amber", low: "green" };
const Chip = ({ c }: { c: any }) => <Link to={`/changes/${c.id}`} className="block rounded-lg border bg-card p-3 text-sm shadow-xs hover:border-primary/40">
  <div className="flex items-center gap-2 text-xs"><span className="font-mono text-primary">{c.number}</span>{c.risk && <Badge tone={RISK[c.risk]}>{c.risk}</Badge>}<span className="ms-auto capitalize text-muted-foreground">{c.type}</span></div>
  <div className="mt-1 line-clamp-2 font-medium">{c.title}</div>{c.start && <div className="mt-1 text-xs text-muted-foreground">{fmt(c.start)}</div>}</Link>;

export default function ChangeOps() {
  const { user } = useAuth(); const admin = user?.role === "admin";
  const [pipe, setPipe] = useState<any[]>([]); const [cal, setCal] = useState<any>(null); const [cab, setCab] = useState<any>(null); const [cfg, setCfg] = useState<any>(null); const [st, setSt] = useState<any>(null);
  const load = () => { api.get("/change-ops/pipeline").then((r) => setPipe(r.data)); api.get("/change-ops/calendar").then((r) => setCal(r.data)); api.get("/change-ops/cab").then((r) => setCab(r.data)); api.get("/change-ops/config").then((r) => setCfg(r.data)); api.get("/change-ops/stats").then((r) => setSt(r.data)); };
  useEffect(load, []);
  const [m, setM] = useState<any>({ title: "Weekly CAB", date: "", minutes: "" });
  const saveCab = () => api.post("/change-ops/cab", { ...m, change_ids: (cab?.suggested_agenda || []).map((c: any) => c.id) }).then(() => { toast.success("CAB meeting saved"); load(); }).catch((x) => toast.error(errMsg(x)));
  const saveFreeze = (list: any[]) => api.put("/change-ops/freeze", list).then(() => { toast.success("Freeze windows saved"); load(); }).catch((x) => toast.error(errMsg(x)));
  const saveRoutes = () => api.put("/change-ops/routes", cfg.routes).then(() => toast.success("Approval routes saved")).catch((x) => toast.error(errMsg(x)));
  const days = cal ? [...new Set(cal.changes.map((c: any) => String(c.start).slice(0, 10)))].sort() as string[] : [];
  return (
    <Page title="Change enablement" icon={RefreshCcw} subtitle="See every change on its way to production, keep the calendar clear, and run CAB." wide
      actions={<Button asChild><Link to="/changes/new"><Plus />New change</Link></Button>}>
      {st && <div className="grid gap-3 sm:grid-cols-4">{[["Changes", st.total], ["High risk", st.by_risk.high || 0], ["Emergency", st.by_type.emergency || 0], ["Success rate", st.success_rate == null ? "–" : `${st.success_rate}%`]].map(([l, v]) =>
        <Card key={l as string}><CardContent className="pt-5"><div className="text-xs text-muted-foreground">{l}</div><div className="text-2xl font-semibold">{v}</div></CardContent></Card>)}</div>}
      <Tabs defaultValue="pipe"><TabsList><TabsTrigger value="pipe"><KanbanSquare />Pipeline</TabsTrigger><TabsTrigger value="cal"><CalendarDays />Calendar</TabsTrigger><TabsTrigger value="cab"><Users />CAB</TabsTrigger><TabsTrigger value="rules"><Snowflake />Freeze & routes</TabsTrigger></TabsList>
        <TabsContent value="pipe" className="pt-4"><div className="grid gap-3 overflow-x-auto" style={{ gridTemplateColumns: `repeat(${pipe.length || 1}, minmax(200px, 1fr))` }}>{pipe.map((c) =>
          <div key={c.state} className="rounded-xl bg-muted/40 p-2"><div className="mb-2 flex items-center justify-between px-1 text-xs font-semibold uppercase text-muted-foreground">{humanize(c.state)}<Badge>{c.items.length}</Badge></div><div className="space-y-2">{c.items.slice(0, 12).map((x: any) => <Chip key={x.id} c={x} />)}</div></div>)}</div></TabsContent>
        <TabsContent value="cal" className="space-y-3 pt-4">
          {cal?.freeze?.map((f: any) => <div key={f.name} className="flex items-center gap-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-800"><Snowflake className="size-4" /><b>{f.name}</b> freeze: {fmt(f.start)} to {fmt(f.end)}{f.reason && ` · ${f.reason}`}</div>)}
          {cal?.clashes?.length > 0 && <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">Heads up: {cal.clashes.map((c: string[]) => c.join(" & ")).join(", ")} touch the same item within 4 hours.</div>}
          {!days.length ? <EmptyState icon={CalendarDays} title="Nothing scheduled" desc="Changes with a planned start show up here." /> : days.map((d) => <div key={d}><div className="mb-1 text-sm font-semibold">{d}</div>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">{cal.changes.filter((c: any) => String(c.start).startsWith(d)).map((c: any) => <Chip key={c.id} c={c} />)}</div></div>)}</TabsContent>
        <TabsContent value="cab" className="grid gap-4 pt-4 lg:grid-cols-2">
          <Card><CardHeader><CardTitle>Next meeting</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
            <div className="grid gap-2 sm:grid-cols-2"><div><Label>Title</Label><Input aria-label="Title" value={m.title} onChange={(e) => setM({ ...m, title: e.target.value })} /></div><div><Label>When</Label><Input aria-label="When" type="datetime-local" value={m.date} onChange={(e) => setM({ ...m, date: e.target.value })} /></div></div>
            <div><Label>Agenda (changes waiting for approval)</Label><div className="mt-1 space-y-2">{cab?.suggested_agenda?.length ? cab.suggested_agenda.map((c: any) => <Chip key={c.id} c={c} />) : <p className="text-muted-foreground">Nothing waiting. Nice!</p>}</div></div>
            <div><Label>Minutes</Label><Textarea aria-label="Minutes" rows={3} value={m.minutes} onChange={(e) => setM({ ...m, minutes: e.target.value })} /></div><Button onClick={saveCab}>Save meeting</Button></CardContent></Card>
          <Card><CardHeader><CardTitle>Past meetings</CardTitle></CardHeader><CardContent className="space-y-2 text-sm">{cab?.meetings?.length ? cab.meetings.map((x: any) => <div key={x.id} className="rounded-lg border p-3"><div className="font-medium">{x.title}</div><div className="text-xs text-muted-foreground">{fmt(x.date)} · {x.change_ids.length} change(s)</div>{x.minutes && <p className="mt-1">{x.minutes}</p>}</div>) : <p className="text-muted-foreground">No meetings yet.</p>}</CardContent></Card></TabsContent>
        <TabsContent value="rules" className="grid gap-4 pt-4 lg:grid-cols-2">{cfg && <>
          <Card><CardHeader className="flex-row items-center justify-between"><CardTitle>Freeze windows</CardTitle>{admin && <Button size="sm" variant="outline" onClick={() => setCfg({ ...cfg, freeze: [...cfg.freeze, { name: "New freeze", start: "", end: "", reason: "" }] })}><Plus />Window</Button>}</CardHeader>
            <CardContent className="space-y-2 text-sm"><p className="text-muted-foreground">Normal and standard changes can't be scheduled or started inside a freeze. Emergency changes still can.</p>
              {cfg.freeze.map((f: any, i: number) => { const up = (p: any) => setCfg({ ...cfg, freeze: cfg.freeze.map((x: any, j: number) => j === i ? { ...x, ...p } : x) });
                return <div key={i} className="grid gap-2 rounded-lg border p-2 sm:grid-cols-[1fr_1fr_1fr_auto]"><Input disabled={!admin} value={f.name} onChange={(e) => up({ name: e.target.value })} /><Input disabled={!admin} type="datetime-local" value={String(f.start).slice(0, 16)} onChange={(e) => up({ start: e.target.value })} /><Input disabled={!admin} type="datetime-local" value={String(f.end).slice(0, 16)} onChange={(e) => up({ end: e.target.value })} />
                  {admin && <Button size="sm" variant="ghost" aria-label="Remove" onClick={() => setCfg({ ...cfg, freeze: cfg.freeze.filter((_: any, j: number) => j !== i) })}><Trash2 /></Button>}</div>; })}
              {admin && <Button size="sm" onClick={() => saveFreeze(cfg.freeze)}>Save windows</Button>}</CardContent></Card>
          <Card><CardHeader><CardTitle>Approval routes</CardTitle></CardHeader><CardContent className="space-y-2 text-sm"><p className="text-muted-foreground">Who approves, step by step, for each change type and risk level. Use admin, group:Name or user:id, separated by commas.</p>
            <table className="w-full"><thead><tr className="text-start text-xs text-muted-foreground"><th>Type</th><th>Low</th><th>Moderate</th><th>High</th></tr></thead><tbody>{Object.entries(cfg.routes).map(([t, lv]: any) => <tr key={t}><td className="py-1 pe-2 capitalize">{t}</td>{["low", "moderate", "high"].map((k) =>
              <td key={k} className="p-1"><Input disabled={!admin} className="h-8" value={(lv[k] || []).join(", ")} onChange={(e) => setCfg({ ...cfg, routes: { ...cfg.routes, [t]: { ...lv, [k]: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) } } })} /></td>)}</tr>)}</tbody></table>
            {admin && <Button size="sm" onClick={saveRoutes}>Save routes</Button>}</CardContent></Card></>}</TabsContent>
      </Tabs>
    </Page>
  );
}

export function MajorIncidents() {
  const [rows, setRows] = useState<any[] | null>(null); const [tr, setTr] = useState<any>(null);
  useEffect(() => { api.get("/major-incidents").then((r) => setRows(r.data)); api.get("/problems/trends").then((r) => setTr(r.data)); }, []);
  const max = tr ? Math.max(1, ...Object.values(tr.by_category) as number[]) : 1;
  return (
    <Page title="Major incidents & trends" icon={Siren} subtitle="Big outages in one place, plus patterns that could use a problem record.">
      <Card><CardHeader><CardTitle>Major incidents</CardTitle></CardHeader><CardContent className="space-y-2 text-sm">{!rows?.length ? <p className="text-muted-foreground">No major incidents. Long may it last.</p> : rows.map((r) =>
        <Link key={r.id} to={`/incidents/${r.id}`} className="flex flex-wrap items-center gap-3 rounded-lg border p-3 hover:border-primary/40"><Badge tone="red">{r.priority}</Badge><span className="font-mono text-xs text-primary">{r.number}</span><span className="font-medium">{r.title}</span>
          <span className="ms-auto text-xs text-muted-foreground">{humanize(r.state)} · {r.updates} update(s) · {r.reviewed ? "reviewed" : "review pending"}</span></Link>)}</CardContent></Card>
      {tr && <div className="grid gap-4 lg:grid-cols-2"><Card><CardHeader><CardTitle>Incidents by category, last {tr.days} days</CardTitle></CardHeader><CardContent className="space-y-1.5 text-sm">{Object.entries(tr.by_category).map(([k, v]: any) =>
        <div key={k} className="flex items-center gap-2"><span className="w-32 truncate capitalize">{humanize(k)}</span><div className="h-2.5 rounded bg-primary/70" style={{ width: `${(70 * v) / max}%` }} /><span className="tabular-nums text-muted-foreground">{v}</span></div>)}</CardContent></Card>
        <Card><CardHeader><CardTitle>Worth a problem record?</CardTitle></CardHeader><CardContent className="space-y-2 text-sm">{!tr.clusters.length ? <p className="text-muted-foreground">No repeating patterns right now.</p> : tr.clusters.map((c: any) =>
          <div key={c.category} className="flex items-center gap-2 rounded-lg border p-3"><span className="flex-1">{c.suggestion}</span><Button size="sm" variant="outline" asChild><Link to="/problems/new">Open problem</Link></Button></div>)}
          {tr.top_words?.length > 0 && <div className="flex flex-wrap gap-1.5 pt-2">{tr.top_words.map(([w, n]: any) => <Badge key={w}>{w} · {n}</Badge>)}</div>}</CardContent></Card></div>}
    </Page>
  );
}
