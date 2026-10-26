import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ReactFlow, Background, Controls, MarkerType, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { api, errMsg } from "../api";
import { Page, Stat, Ico } from "../ui";
const IC: Record<string, ReactNode> = { server: <Ico n="server" />, application: <Ico n="app" />, database: <Ico n="db" />, network: <Ico n="net" />, laptop: <Ico n="laptop" />, cloud_service: <Ico n="cloud" />, storage: <Ico n="disk" /> };
const dq = (s: number) => (s >= 80 ? "text-emerald-600" : s >= 60 ? "text-amber-600" : "text-red-600");
const SAMPLE = JSON.stringify({ source: "agentless-scan", items: [{ name: "web-02", ci_class: "server", ip: "10.10.5.12", os: "Ubuntu 24.04", serial: "W2", environment: "production", owner: "Web" }], relations: [{ parent: "web-02", child: "core-sw-01", type: "connects_to" }] }, null, 2);
export default function Cmdb() {
  const [cis, setCis] = useState<any[]>([]); const [q, setQ] = useState<any>(null); const [sel, setSel] = useState<number | null>(null); const [g, setG] = useState<any>(null);
  const [imp, setImp] = useState(SAMPLE); const [msg, setMsg] = useState("");
  const load = () => { api.get("/records/ci").then((r) => { setCis(r.data); if (!sel && r.data.length) setSel(r.data.find((c: any) => c.title === "core-sw-01")?.id ?? r.data[0].id); }); api.get("/cmdb/quality").then((r) => setQ(r.data)); };
  useEffect(() => { load(); }, []);
  useEffect(() => { if (sel) api.get(`/cmdb/ci/${sel}/graph`).then((r) => setG(r.data)); }, [sel]);
  const { nodes, edges } = useMemo(() => {
    if (!g) return { nodes: [] as Node[], edges: [] as Edge[] };
    const n = g.nodes.length; const nodes: Node[] = g.nodes.map((x: any, i: number) => {
      const center = x.id === sel; const ang = (2 * Math.PI * i) / Math.max(1, n - 1);
      return { id: String(x.id), position: center ? { x: 300, y: 200 } : { x: 300 + 260 * Math.cos(ang), y: 200 + 170 * Math.sin(ang) },
        data: { label: <div className="text-xs"><div className="mb-1 flex justify-center text-indigo-500">{IC[x.ci_class] || <Ico n="pkg" />}</div><b>{x.title}</b><div className={dq(x.dq_score)}>DQ {x.dq_score}</div></div> },
        style: { border: center ? "2px solid #6366f1" : g.impacted.includes(x.id) ? "2px solid #ef4444" : "1px solid hsl(var(--border))", borderRadius: 10, width: 150, background: "hsl(var(--card))", color: "hsl(var(--foreground))", boxShadow: "0 1px 3px rgb(15 23 42 / .08)" } };
    });
    const edges: Edge[] = g.edges.map((e: any, i: number) => ({ id: "e" + i, source: String(e.source), target: String(e.target), label: e.rel_type, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: "#94a3b8" }, labelStyle: { fontSize: 10, fill: "#64748b" }, labelBgStyle: { fill: "hsl(var(--card))" } }));
    return { nodes, edges };
  }, [g, sel]);
  const runImport = async () => { try { const r = await api.post("/cmdb/discovery", JSON.parse(imp)); setMsg(`Discovery: ${r.data.created} created, ${r.data.updated} updated, ${r.data.relations} relations`); load(); } catch (x) { setMsg(errMsg(x)); } };
  return (
    <Page title="CMDB & Service Map" actions={<Link className="btn" to="/m/ci/new"><Ico n="plus" />New CI</Link>}>
      {q && <div className="grid grid-cols-2 lg:grid-cols-5 gap-4"><Stat label="Configuration items" value={q.ci_count} /><Stat label="Avg data quality" value={`${q.avg_dq_score}`} tone={dq(q.avg_dq_score)} />
        <Stat label="Orphan CIs" value={q.orphans} tone="text-amber-600" /><Stat label="Not discovered" value={q.undiscovered} tone="text-amber-600" /><Stat label="Classes" value={Object.keys(q.by_class).length} /></div>}
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="card overflow-hidden lg:col-span-1 max-h-[520px] overflow-y-auto"><table className="w-full"><thead><tr><th className="th">CI</th><th className="th">Class</th><th className="th">DQ</th></tr></thead>
          <tbody>{cis.map((c) => <tr key={c.id} onClick={() => setSel(c.id)} className={`cursor-pointer hover:bg-slate-50 ${sel === c.id ? "bg-brand-50" : ""}`}><td className="td"><span className="me-1.5 text-muted-foreground">{IC[c.data.ci_class]}</span><Link className="text-brand-600" to={`/m/ci/${c.id}`}>{c.title}</Link></td><td className="td text-xs">{c.data.ci_class}</td><td className={`td font-bold ${dq(c.data.dq_score)}`}>{c.data.dq_score}</td></tr>)}</tbody></table></div>
        <div className="card lg:col-span-2 h-[520px]"><div className="px-4 pt-3 text-sm font-semibold">Dependency map {g && <span className="font-normal text-slate-500">· {g.ci.title}: <span className="text-red-600">{g.impacted.length} impacted CI(s)</span> if it fails</span>}</div>
          <div className="h-[480px]"><ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }}><Background gap={20} size={1} color="hsl(var(--border))" /><Controls /></ReactFlow></div></div>
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="card p-4"><h3 className="font-semibold mb-2">Data quality — worst CIs</h3>{q?.worst.map((w: any) => <div key={w.id} className="text-sm py-1 flex justify-between"><Link className="text-brand-600" to={`/m/ci/${w.id}`}>{w.title}</Link><span><b className={dq(w.dq_score)}>{w.dq_score}</b> <span className="text-xs text-slate-400">missing: {w.missing?.join(", ") || "discovery"}</span></span></div>)}</div>
        <div className="card p-4 space-y-2"><h3 className="font-semibold">Discovery import (API: POST /api/cmdb/discovery)</h3><textarea className="input font-mono text-xs h-40" value={imp} onChange={(e) => setImp(e.target.value)} />
          <button className="btn" onClick={runImport}>Run import</button> <span className="text-sm text-slate-600">{msg}</span></div>
      </div>
    </Page>
  );
}
