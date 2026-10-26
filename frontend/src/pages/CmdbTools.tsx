import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Activity, FileSpreadsheet, HeartPulse, KeyRound, Network, Plus, Settings2, Trash2, Zap } from "lucide-react";
import { api, errMsg } from "../api";
import { useAuth } from "../auth";
import { Page } from "../ui";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/misc";
import { humanize } from "@/lib/utils";

const TONE: Record<string, any> = { healthy: "green", degraded: "amber", critical: "red" };
const FILL: Record<string, string> = { healthy: "#16a34a", degraded: "#F59E0B", critical: "#E5002B" };

function ServiceMap({ m, onPick }: { m: any; onPick: (id: number) => void }) {
  const lay = useMemo(() => { if (!m) return null;
    const ids = m.nodes.map((n: any) => n.id); const parents: Record<number, number[]> = {}; m.edges.forEach((e: any) => { (parents[e.target] ||= []).push(e.source); });
    const depth: Record<number, number> = {}; const d = (id: number, seen = new Set<number>()): number => { if (depth[id] != null) return depth[id]; if (seen.has(id)) return 0; seen.add(id); const p = parents[id] || []; return depth[id] = p.length ? 1 + Math.max(...p.map((x) => d(x, seen))) : 0; };
    const linked = new Set(m.edges.flatMap((e: any) => [e.source, e.target])); const nodes = m.nodes.filter((n: any) => linked.has(n.id));
    ids.forEach((i: number) => d(i)); const cols: Record<number, any[]> = {}; nodes.forEach((n: any) => (cols[depth[n.id]] ||= []).push(n));
    const pos: Record<number, [number, number]> = {}; Object.entries(cols).forEach(([c, ns]) => ns.forEach((n, i) => { pos[n.id] = [40 + +c * 220, 30 + i * 56]; }));
    const h = 60 + Math.max(...Object.values(cols).map((c) => c.length)) * 56; return { nodes, pos, h, w: 80 + Object.keys(cols).length * 220 }; }, [m]);
  if (!lay) return null;
  return <div className="overflow-auto rounded-xl border bg-card"><svg width={lay.w} height={lay.h} role="img" aria-label="Service map">
    {m.edges.map((e: any, i: number) => { const a = lay.pos[e.source], b = lay.pos[e.target]; if (!a || !b) return null; return <path key={i} d={`M${a[0] + 170},${a[1] + 18} C${a[0] + 200},${a[1] + 18} ${b[0] - 30},${b[1] + 18} ${b[0]},${b[1] + 18}`} fill="none" stroke="#c7cbe0" strokeWidth={1.5}><title>{e.label}</title></path>; })}
    {lay.nodes.map((n: any) => { const [x, y] = lay.pos[n.id]; return <g key={n.id} transform={`translate(${x},${y})`} className="cursor-pointer" onClick={() => onPick(n.id)}>
      <rect width={170} height={36} rx={8} fill="#fff" stroke={FILL[n.status]} strokeWidth={1.5} /><circle cx={14} cy={18} r={5} fill={FILL[n.status]} />
      <text x={26} y={16} fontSize={11} fontWeight={600} fill="#011C25">{n.title.slice(0, 22)}</text><text x={26} y={29} fontSize={9.5} fill="#64748b">{humanize(n.ci_class || "")} · {n.score}</text></g>; })}
  </svg></div>;
}

export default function CmdbTools() {
  const { user } = useAuth(); const admin = user?.role === "admin";
  const [m, setM] = useState<any>(null); const [h, setH] = useState<any>(null); const [cfg, setCfg] = useState<any>(null); const [sel, setSel] = useState<number | null>(null); const [im, setIm] = useState<any>(null); const [tab, setTab] = useState("map");
  const load = () => { api.get("/cmdb/service-map").then((r) => setM(r.data)); api.get("/cmdb/health").then((r) => setH(r.data)); api.get("/cmdb/config").then((r) => setCfg(r.data)); };
  useEffect(load, []);
  useEffect(() => { if (sel) api.get(`/cmdb/ci/${sel}/impact`).then((r) => setIm(r.data)); }, [sel]);
  const pick = (id: number) => { setSel(id); setTab("impact"); };
  const [csv, setCsv] = useState("name,ci_class,ip,serial,environment,owner\nweb-07,server,10.0.5.7,SRV-WEB-07,production,Web team\napp-billing,application,,,production,Finance IT");
  const [map, setMap] = useState<Record<string, string>>({}); const [res, setRes] = useState<any>(null);
  const headers = csv.split("\n")[0]?.split(",").map((s) => s.trim()).filter(Boolean) || [];
  const attrs = ["name", "ci_class", "_skip", ...new Set((cfg?.classes || []).flatMap((c: any) => c.attributes.map((a: any) => a.key)) as string[])];
  const run = (dry: boolean) => api.post("/cmdb/import", { csv, mapping: map, dry_run: dry }).then((r) => { setRes(r.data); if (!dry) { toast.success(`Imported: ${r.data.summary.create} new, ${r.data.summary.update} updated`); load(); } }).catch((x) => toast.error(errMsg(x)));
  return (
    <Page title="CMDB insights" icon={Network} subtitle="How your services hang together, how healthy they are, and what breaks if something goes down." wide>
      {h && <div className="grid gap-3 sm:grid-cols-4">{[["Average health", h.average ?? "–"], ["Healthy", h.by_status.healthy || 0], ["Degraded", h.by_status.degraded || 0], ["Critical", h.by_status.critical || 0]].map(([l, v]) =>
        <Card key={l as string}><CardContent className="pt-5"><div className="text-xs text-muted-foreground">{l}</div><div className="text-2xl font-semibold">{v}</div></CardContent></Card>)}</div>}
      <Tabs value={tab} onValueChange={setTab}><TabsList><TabsTrigger value="map"><Network />Service map</TabsTrigger><TabsTrigger value="health"><HeartPulse />Health</TabsTrigger><TabsTrigger value="impact"><Zap />Impact</TabsTrigger><TabsTrigger value="import"><FileSpreadsheet />Import</TabsTrigger><TabsTrigger value="model"><Settings2 />Classes & relationships</TabsTrigger></TabsList>
        <TabsContent value="map" className="pt-4"><p className="mb-2 text-sm text-muted-foreground">Arrows go from an item to what it relies on. Click any box to see its impact.</p><ServiceMap m={m} onPick={pick} /></TabsContent>
        <TabsContent value="health" className="pt-4"><Card><CardContent className="divide-y p-0 text-sm">{h?.rows.slice(0, 40).map((r: any) => <button key={r.id} onClick={() => pick(r.id)} className="flex w-full items-center gap-3 px-4 py-2.5 text-start hover:bg-accent">
          <Badge tone={TONE[r.status]}>{r.score}</Badge><span className="font-mono text-xs text-primary">{r.number}</span><span className="font-medium">{r.title}</span><span className="text-xs capitalize text-muted-foreground">{humanize(r.ci_class || "")}</span>
          <span className="ms-auto text-xs text-muted-foreground">{r.open_incidents} open incident(s) · {r.open_changes} change(s)</span></button>)}</CardContent></Card></TabsContent>
        <TabsContent value="impact" className="space-y-4 pt-4">
          <NativeSelect className="max-w-sm" value={sel ?? ""} onChange={(e) => setSel(+e.target.value)}><option value="">Pick a configuration item…</option>{m?.nodes.map((n: any) => <option key={n.id} value={n.id}>{n.title}</option>)}</NativeSelect>
          {im && <><div className="rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-sm">{im.summary}</div>
            <div className="grid gap-4 lg:grid-cols-3">{[["Relies on", im.depends_on], ["Would be affected", im.impacted], ["Business services hit", im.services]].map(([t, rows]: any) =>
              <Card key={t}><CardHeader><CardTitle>{t} <Badge className="ms-1">{rows.length}</Badge></CardTitle></CardHeader><CardContent className="space-y-1.5 text-sm">{!rows.length ? <p className="text-muted-foreground">None</p> : rows.map((r: any) =>
                <div key={r.id} className="flex items-center gap-2"><Badge tone={TONE[r.status]}>{r.score}</Badge><Link className="hover:underline" to={`/cmdb`}>{r.title}</Link>{r.criticality === "high" && <Badge tone="red">critical item</Badge>}</div>)}</CardContent></Card>)}</div>
            <Card><CardHeader><CardTitle>Open tickets on these items</CardTitle></CardHeader><CardContent className="space-y-1.5 text-sm">{!im.open_tickets.length ? <p className="text-muted-foreground">Nothing open. 🎉</p> : im.open_tickets.map((t: any) =>
              <Link key={t.id} to={`/${t.module === "incident" ? "incidents" : t.module === "change" ? "changes" : "problems"}/${t.id}`} className="flex items-center gap-2 hover:underline"><Badge>{t.priority}</Badge><span className="font-mono text-xs">{t.number}</span>{t.title}</Link>)}</CardContent></Card></>}</TabsContent>
        <TabsContent value="import" className="grid gap-4 pt-4 lg:grid-cols-2">
          <Card><CardHeader><CardTitle>1. Paste a CSV (up to 500 rows)</CardTitle></CardHeader><CardContent className="space-y-3 text-sm"><Textarea rows={8} className="font-mono text-xs" value={csv} onChange={(e) => { setCsv(e.target.value); setRes(null); }} />
            <Input type="file" accept=".csv" aria-label="CSV file" onChange={(e) => e.target.files?.[0]?.text().then((t) => { setCsv(t); setRes(null); })} />
            <div className="font-medium">2. Match columns</div><div className="grid gap-2 sm:grid-cols-2">{headers.map((hh) => <div key={hh} className="flex items-center gap-2"><span className="w-28 truncate font-mono text-xs">{hh}</span>
              <NativeSelect className="h-8" value={map[hh] || (attrs.includes(hh.toLowerCase()) ? hh.toLowerCase() : "")} onChange={(e) => setMap({ ...map, [hh]: e.target.value })}><option value="">same name</option>{attrs.map((a) => <option key={a} value={a}>{a === "_skip" ? "skip column" : a}</option>)}</NativeSelect></div>)}</div>
            <div className="flex gap-2"><Button variant="outline" onClick={() => run(true)}>3. Preview (dry run)</Button><Button disabled={!res?.dry_run} onClick={() => run(false)}>4. Import</Button></div></CardContent></Card>
          <Card><CardHeader><CardTitle>Preview</CardTitle></CardHeader><CardContent className="text-sm">{!res ? <p className="text-muted-foreground">Run a dry run to see exactly what will change. Nothing is saved until you click Import.</p> : <>
            <div className="mb-3 flex flex-wrap gap-2"><Badge tone="green">{res.summary.create} new</Badge><Badge tone="amber">{res.summary.update} updates</Badge><Badge>{res.summary.unchanged} unchanged</Badge><Badge tone="red">{res.summary.error} errors</Badge>{!res.dry_run && <Badge tone="violet">saved</Badge>}</div>
            <div className="max-h-96 space-y-1 overflow-auto">{res.rows.map((r: any) => <div key={r.row} className="flex gap-2 text-xs"><span className="w-10 text-muted-foreground">#{r.row}</span><Badge tone={r.action === "error" ? "red" : r.action === "create" ? "green" : r.action === "update" ? "amber" : undefined}>{r.action}</Badge>
              <span>{r.name}{r.match && ` → ${r.match} (matched by ${r.rule})`}{r.message && ` ${r.message}`}{r.changes && ` · ${Object.keys(r.changes).join(", ")}`}</span></div>)}</div></>}</CardContent></Card></TabsContent>
        <TabsContent value="model" className="grid gap-4 pt-4 lg:grid-cols-2">{cfg && <ModelEditor cfg={cfg} admin={admin} reload={load} />}</TabsContent>
      </Tabs>
    </Page>
  );
}

function ModelEditor({ cfg, admin, reload }: any) {
  const [cl, setCl] = useState<any[]>(cfg.classes); const [rt, setRt] = useState<any[]>(cfg.rel_types); const [idn, setIdn] = useState<string>(cfg.identity.map((r: string[]) => r.join(" + ")).join("\n"));
  const err = (x: any) => toast.error(errMsg(x));
  const save = async () => { try { await api.put("/cmdb/classes", cl); await api.put("/cmdb/rel-types", rt); await api.put("/cmdb/identity", idn.split("\n").map((l) => l.split("+").map((s) => s.trim()).filter(Boolean)).filter((r) => r.length)); toast.success("CMDB model saved"); reload(); } catch (x) { err(x); } };
  const upC = (i: number, p: any) => setCl(cl.map((c, j) => j === i ? { ...c, ...p } : c));
  return <>
    <Card><CardHeader className="flex-row items-center justify-between"><CardTitle>CI classes</CardTitle>{admin && <Button size="sm" variant="outline" onClick={() => setCl([...cl, { key: `class_${cl.length + 1}`, label: "New class", attributes: [] }])}><Plus />Class</Button>}</CardHeader>
      <CardContent className="space-y-3 text-sm">{cl.map((c, i) => <div key={i} className="rounded-lg border p-3"><div className="flex gap-2"><Input disabled={!admin} className="h-8" value={c.label} onChange={(e) => upC(i, { label: e.target.value })} /><Input disabled={!admin} className="h-8 w-40 font-mono text-xs" value={c.key} onChange={(e) => upC(i, { key: e.target.value })} />
        <NativeSelect disabled={!admin} className="h-8 w-36" value={c.parent || ""} onChange={(e) => upC(i, { parent: e.target.value || null })}><option value="">No parent</option>{cl.filter((x) => x.key !== c.key).map((x) => <option key={x.key} value={x.key}>{x.label}</option>)}</NativeSelect></div>
        <div className="mt-2 flex flex-wrap gap-1.5">{c.attributes.map((a: any, k: number) => <span key={k} className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs">{a.label}{a.required && " *"}{admin && <button aria-label="Remove attribute" onClick={() => upC(i, { attributes: c.attributes.filter((_: any, x: number) => x !== k) })}><Trash2 className="size-3" /></button>}</span>)}
          {admin && <button className="rounded-full border border-dashed px-2 py-0.5 text-xs text-muted-foreground" onClick={() => { const l = prompt("Attribute name?"); if (l) upC(i, { attributes: [...c.attributes, { key: l.toLowerCase().replace(/\W+/g, "_"), label: l, required: confirm("Required for data quality?") }] }); }}>+ attribute</button>}</div></div>)}</CardContent></Card>
    <div className="space-y-4"><Card><CardHeader className="flex-row items-center justify-between"><CardTitle>Relationship types</CardTitle>{admin && <Button size="sm" variant="outline" onClick={() => setRt([...rt, { key: `rel_${rt.length + 1}`, label: "New relationship", reverse: "" }])}><Plus />Type</Button>}</CardHeader>
      <CardContent className="space-y-2">{rt.map((r, i) => <div key={i} className="grid grid-cols-3 gap-2">{["key", "label", "reverse"].map((k) => <Input key={k} disabled={!admin} className="h-8 text-xs" placeholder={k} value={r[k]} onChange={(e) => setRt(rt.map((x, j) => j === i ? { ...x, [k]: e.target.value } : x))} />)}</div>)}</CardContent></Card>
      <Card><CardHeader><CardTitle>Identity rules</CardTitle></CardHeader><CardContent className="space-y-2 text-sm"><p className="text-muted-foreground">How imports find an existing item. One rule per line, tried top to bottom. Join attributes with +.</p>
        <Textarea disabled={!admin} rows={4} className="font-mono text-xs" value={idn} onChange={(e) => setIdn(e.target.value)} /></CardContent></Card>
      {admin && <Button onClick={save}>Save model</Button>}</div></>;
}

export function ItamCompliance() {
  const [lc, setLc] = useState<any>(null); const [ct, setCt] = useState<any[]>([]);
  useEffect(() => { api.get("/itam/licence-compliance").then((r) => setLc(r.data)); api.get("/itam/contracts").then((r) => setCt(r.data)); }, []);
  const ST: Record<string, any> = { over_deployed: "red", under_utilized: "amber", compliant: "green" };
  return (
    <Page title="Licences & contracts" icon={KeyRound} subtitle="Are we using what we have, and what needs renewing soon?"
      actions={<Button variant="outline" asChild><Link to="/m/purchase_order"><Activity />Purchase orders</Link></Button>}>
      {lc && <div className="grid gap-3 sm:grid-cols-4">{[["Compliant", lc.by_status.compliant || 0], ["Over-deployed", lc.by_status.over_deployed || 0], ["Seats over", lc.over_deployed_seats], ["Unused seats", lc.unused_seats]].map(([l, v]) =>
        <Card key={l as string}><CardContent className="pt-5"><div className="text-xs text-muted-foreground">{l}</div><div className="text-2xl font-semibold">{v}</div></CardContent></Card>)}</div>}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card><CardHeader><CardTitle>Licence compliance</CardTitle></CardHeader><CardContent className="space-y-2 text-sm">{lc?.rows.map((r: any) => <div key={r.id} className="space-y-1">
          <div className="flex items-center gap-2"><span className="font-medium">{r.title}</span><Badge tone={ST[r.status]}>{humanize(r.status || "")}</Badge><span className="ms-auto tabular-nums text-xs text-muted-foreground">{r.seats_used} / {r.seats_owned} seats</span></div>
          <div className="h-2 overflow-hidden rounded bg-muted"><div className="h-full rounded" style={{ width: `${Math.min(100, r.utilization_pct || 0)}%`, background: r.status === "over_deployed" ? "#E5002B" : r.status === "under_utilized" ? "#F59E0B" : "#081160" }} /></div></div>)}</CardContent></Card>
        <Card><CardHeader><CardTitle>Contract renewals</CardTitle></CardHeader><CardContent className="divide-y p-0 text-sm">{ct.map((c) => <Link key={c.id} to={`/m/contract/${c.id}`} className="flex items-center gap-2 px-5 py-2.5 hover:bg-accent">
          <span className="font-medium">{c.title}</span><span className="text-xs text-muted-foreground">{c.vendor} · {humanize(c.type || "")}</span>
          <Badge className="ms-auto" tone={c.renewal === "overdue" ? "red" : c.renewal === "soon" ? "amber" : undefined}>{c.days_left == null ? "no end date" : c.days_left < 0 ? `ended ${-c.days_left}d ago` : `${c.days_left} days left`}</Badge></Link>)}</CardContent></Card>
      </div>
    </Page>
  );
}
