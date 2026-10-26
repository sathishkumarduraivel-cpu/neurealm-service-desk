import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertOctagon, ArrowRight, Bot, CheckCircle2, Clock, Gauge, ShieldCheck, Timer } from "lucide-react";
import { api, type Rec } from "../api";
import { useAuth } from "../auth";
import { Page, Priority, Stat } from "../ui";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Avatar, Skeleton } from "@/components/ui/misc";
import { ChartTooltip, PALETTE, PRIORITY_COLORS, axis, grid } from "@/components/charts";
import { relTime } from "@/lib/utils";

const pct = (a: number, b: number) => (b ? Math.round((100 * (a - b)) / b) : a ? 100 : 0);
export default function Dashboard() {
  const { user } = useAuth(); const [m, setM] = useState<any>(null); const [recent, setRecent] = useState<Rec[] | null>(null);
  useEffect(() => { api.get("/dashboard/metrics").then((r) => setM(r.data)); api.get("/records/incident", { params: { limit: 8 } }).then((r) => setRecent(r.data.slice(0, 8))).catch(() => setRecent([])); }, []);
  const hour = new Date().getHours(); const greet = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  if (!m) return <Page title="Dashboard" icon={Gauge}><div className="grid grid-cols-2 gap-4 lg:grid-cols-6">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-[104px]" />)}</div><div className="grid gap-4 lg:grid-cols-3"><Skeleton className="h-80 lg:col-span-2" /><Skeleton className="h-80" /></div></Page>;
  const t = m.trend as any[]; const sum = (a: any[], k: string) => a.reduce((s, x) => s + x[k], 0);
  const cNow = sum(t.slice(7), "created"), cPrev = sum(t.slice(0, 7), "created"), rNow = sum(t.slice(7), "resolved"), rPrev = sum(t.slice(0, 7), "resolved");
  const totalOpen = m.by_priority.reduce((s: number, x: any) => s + x.value, 0);
  return (
    <Page title={`${greet}, ${user?.full_name.split(" ")[0]}`} subtitle="Here's what's happening across your service desk today." actions={<><Button variant="outline" asChild><Link to="/incidents">View queue</Link></Button><Button asChild><Link to="/incidents/new">New incident</Link></Button></>}>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        <Stat label="Open incidents" value={m.open_incidents} icon={AlertOctagon} delta={pct(cNow, cPrev)} deltaGood="down" hint="new vs last wk" />
        <Stat label="Critical (P1) open" value={m.p1_open} icon={AlertOctagon} tone={m.p1_open ? "text-red-600" : ""} hint={m.p1_open ? "Needs attention" : "All clear"} />
        <Stat label="Resolved (7d)" value={rNow} icon={CheckCircle2} delta={pct(rNow, rPrev)} hint="vs prior 7d" />
        <Stat label="SLA compliance" value={`${m.sla_compliance_pct}%`} icon={ShieldCheck} tone={m.sla_compliance_pct >= 90 ? "text-emerald-600" : m.sla_compliance_pct >= 75 ? "text-amber-600" : "text-red-600"} hint={`${m.sla_breached} breached · ${m.sla_at_risk} at risk`} />
        <Stat label="MTTR" value={<>{m.mttr_hours}<span className="ms-0.5 text-sm font-medium text-muted-foreground">h</span></>} icon={Timer} hint="mean time to resolve" />
        <Stat label="AI auto-routed" value={`${m.ai_auto_routed_pct}%`} icon={Bot} tone="text-brand-600" hint="of all incidents" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2"><CardHeader><div><CardTitle>Incident volume</CardTitle><CardDescription>Created vs resolved · last 14 days</CardDescription></div>
          <div className="flex gap-4 text-xs text-muted-foreground"><span className="flex items-center gap-1.5"><span className="size-2 rounded-full" style={{ background: PALETTE[0] }} />Created <b className="text-foreground tabular-nums">{cNow + cPrev}</b></span><span className="flex items-center gap-1.5"><span className="size-2 rounded-full" style={{ background: PALETTE[2] }} />Resolved <b className="text-foreground tabular-nums">{rNow + rPrev}</b></span></div></CardHeader>
          <CardContent className="h-[260px] ps-1"><ResponsiveContainer><AreaChart data={t} margin={{ left: -16, right: 8, top: 8 }}>
            <defs>{[0, 2].map((i) => <linearGradient key={i} id={`g${i}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={PALETTE[i]} stopOpacity={0.25} /><stop offset="100%" stopColor={PALETTE[i]} stopOpacity={0} /></linearGradient>)}</defs>
            <CartesianGrid {...grid} /><XAxis dataKey="date" {...axis} /><YAxis allowDecimals={false} {...axis} /><Tooltip content={<ChartTooltip />} cursor={{ stroke: "hsl(var(--border))" }} />
            <Area type="monotone" dataKey="created" name="Created" stroke={PALETTE[0]} strokeWidth={2} fill="url(#g0)" /><Area type="monotone" dataKey="resolved" name="Resolved" stroke={PALETTE[2]} strokeWidth={2} fill="url(#g2)" /></AreaChart></ResponsiveContainer></CardContent></Card>
        <Card><CardHeader><div><CardTitle>Open by priority</CardTitle><CardDescription>{totalOpen} open incidents</CardDescription></div></CardHeader>
          <CardContent><div className="relative h-[170px]"><ResponsiveContainer><PieChart><Pie data={m.by_priority} dataKey="value" nameKey="name" innerRadius={56} outerRadius={78} paddingAngle={2} strokeWidth={0}>
            {m.by_priority.map((x: any) => <Cell key={x.name} fill={PRIORITY_COLORS[x.name]} />)}</Pie><Tooltip content={<ChartTooltip />} /></PieChart></ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center"><span className="text-2xl font-semibold tabular-nums">{totalOpen}</span><span className="text-[11px] text-muted-foreground">open</span></div></div>
            <div className="mt-3 space-y-2">{m.by_priority.map((x: any) => <div key={x.name} className="flex items-center gap-2 text-sm"><span className="size-2 rounded-sm" style={{ background: PRIORITY_COLORS[x.name] }} /><span className="flex-1">{{ P1: "Critical", P2: "High", P3: "Moderate", P4: "Low" }[x.name as "P1"]}</span>
              <span className="w-24"><span className="block h-1.5 rounded-full bg-muted"><span className="block h-full rounded-full" style={{ width: `${totalOpen ? (100 * x.value) / totalOpen : 0}%`, background: PRIORITY_COLORS[x.name] }} /></span></span><span className="w-6 text-end font-medium tabular-nums">{x.value}</span></div>)}</div></CardContent></Card>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card><CardHeader><div><CardTitle>By category</CardTitle><CardDescription>AI-classified</CardDescription></div></CardHeader><CardContent className="h-[240px] ps-1">
          <ResponsiveContainer><BarChart data={m.by_category} margin={{ left: -16, right: 8 }}><CartesianGrid {...grid} /><XAxis dataKey="name" {...axis} interval={0} tick={{ ...axis.tick, fontSize: 10 }} /><YAxis allowDecimals={false} {...axis} />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: "hsl(var(--muted))" }} /><Bar dataKey="value" name="Incidents" fill={PALETTE[0]} radius={[4, 4, 0, 0]} maxBarSize={28} /></BarChart></ResponsiveContainer></CardContent></Card>
        <Card><CardHeader><div><CardTitle>Open by team</CardTitle><CardDescription>Current workload per assignment group</CardDescription></div></CardHeader><CardContent className="space-y-3">
          {m.by_group.slice(0, 7).map((g: any, i: number) => { const max = Math.max(...m.by_group.map((x: any) => x.value)); return <div key={g.name} className="text-sm"><div className="flex justify-between"><span className="truncate">{g.name}</span><span className="font-medium tabular-nums">{g.value}</span></div>
            <div className="mt-1 h-1.5 rounded-full bg-muted"><div className="h-full rounded-full" style={{ width: `${(100 * g.value) / max}%`, background: PALETTE[i % PALETTE.length] }} /></div></div>; })}</CardContent></Card>
        <Card><CardHeader><div><CardTitle>Recent activity</CardTitle><CardDescription>Latest incidents</CardDescription></div><Link to="/incidents" className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">View all<ArrowRight className="size-3" /></Link></CardHeader>
          <CardContent className="space-y-0.5">{recent === null ? [...Array(5)].map((_, i) => <Skeleton key={i} className="mb-2 h-10" />) : recent.slice(0, 6).map((r) =>
            <Link key={r.id} to={`/incidents/${r.id}`} className="-mx-2 flex items-center gap-3 rounded-md px-2 py-2 hover:bg-muted/50"><Avatar name={r.requester?.full_name} size={28} />
              <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium">{r.title}</div><div className="flex items-center gap-1.5 text-xs text-muted-foreground"><span className="font-mono">{r.number}</span>·<Clock className="size-3" />{relTime(r.created_at)}</div></div>
              <div className="flex flex-col items-end gap-1"><Priority p={r.priority} /></div></Link>)}</CardContent></Card>
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        {[...Object.entries(m.totals).map(([k, v]: any) => [`${k[0].toUpperCase()}${k.slice(1)}s`, v, `/${k}s`]), ["Pending approvals", m.pending_approvals, "/approvals"]].map(([l, v, to]) =>
          <Link key={l} to={to} className="group flex items-center justify-between rounded-lg border bg-card px-4 py-3 shadow-xs transition-colors hover:border-primary/30"><div><div className="text-xs text-muted-foreground">{l}</div><div className="text-lg font-semibold tabular-nums">{v}</div></div><ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" /></Link>)}
      </div>
    </Page>
  );
}
