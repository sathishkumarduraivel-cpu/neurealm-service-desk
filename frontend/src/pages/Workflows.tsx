import { useCallback, useEffect, useState } from "react";
import { ReactFlow, Background, Controls, addEdge, applyEdgeChanges, applyNodeChanges, Handle, Position, MarkerType, type Connection, type Edge, type EdgeChange, type Node, type NodeChange } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { toast } from "sonner";
import { GitBranch, History, Play, Plus, Power, RotateCcw, Save, Trash2 } from "lucide-react";
import { api, errMsg } from "../api";
import { useModules } from "../modules";
import { Page, fmt } from "../ui";
import { useCustomFields } from "@/components/CustomFields";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, NativeSelect, Textarea } from "@/components/ui/input";
import { Switch, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/misc";
import { cn, humanize } from "@/lib/utils";

const box = "rounded-lg border-2 bg-white px-3 py-2 text-xs shadow-sm min-w-[170px]";
const TriggerNode = ({ data }: any) => <div className={cn(box, "border-[#1863DC]")}><div className="font-semibold text-[#1863DC]">⚡ Trigger</div>{data.label}<Handle type="source" position={Position.Right} /></div>;
const ConditionNode = ({ data }: any) => <div className={cn(box, "border-[#F59E0B]")}><Handle type="target" position={Position.Left} /><div className="font-semibold text-[#F59E0B]">◆ Condition</div>{data.label || `${data.field} ${data.op} ${data.value ?? ""}`}
  <Handle id="true" type="source" position={Position.Right} style={{ top: "35%", background: "#10b981" }} /><Handle id="false" type="source" position={Position.Right} style={{ top: "75%", background: "#E5002B" }} />
  <div className="mt-1 flex justify-end gap-1 text-[9px]"><span className="text-emerald-600">yes</span><span className="text-[#E5002B]">no</span></div></div>;
const ActionNode = ({ data }: any) => <div className={cn(box, data.action === "approval" ? "border-[#081160]" : "border-emerald-500")}><Handle type="target" position={Position.Left} />
  <div className={cn("font-semibold", data.action === "approval" ? "text-[#081160]" : "text-emerald-600")}>▶ {humanize(data.action || "action")}</div>{data.label}
  {data.action === "approval" ? <><Handle id="true" type="source" position={Position.Right} style={{ top: "35%", background: "#10b981" }} /><Handle id="false" type="source" position={Position.Right} style={{ top: "75%", background: "#E5002B" }} />
    <div className="mt-1 flex justify-end gap-1 text-[9px]"><span className="text-emerald-600">approved</span><span className="text-[#E5002B]">rejected</span></div></> : <Handle type="source" position={Position.Right} />}</div>;
const nodeTypes = { trigger: TriggerNode, condition: ConditionNode, action: ActionNode };
const TRIGGERS: [string, string][] = [["created", "Record created"], ["updated", "Record updated"], ["state_changed", "State changes"], ["field_changed", "A field changes"], ["field_condition", "A field condition is met"], ["sla_warning", "SLA at risk"], ["sla_breach", "SLA breached"], ["schedule", "On a schedule"]];
const ACTIONS: [string, string][] = [["set_field", "Set a field"], ["assign", "Assign"], ["notify", "Notify"], ["add_comment", "Add a note"], ["create_record", "Create related record"], ["approval", "Ask for approval"], ["webhook", "Call a webhook"], ["wait", "Wait"], ["connector", "Send to connector"], ["run_autoresolve", "Run auto-resolve"]];
const OPS: [string, string][] = [["eq", "equals"], ["neq", "is not"], ["contains", "contains"], ["in", "is one of"], ["gt", ">"], ["lt", "<"], ["empty", "is empty"], ["filled", "is filled"], ["changed", "changed"]];
const STD = ["title", "description", "state", "priority", "category", "impact", "urgency", "assignment_group"];
const deco = (e: any): Edge => ({ ...e, id: e.id || `e${e.source}-${e.target}-${e.sourceHandle || ""}`, markerEnd: { type: MarkerType.ArrowClosed }, label: e.sourceHandle === "false" ? "no" : e.sourceHandle === "true" ? "yes" : undefined, style: { stroke: e.sourceHandle === "false" ? "#E5002B" : e.sourceHandle === "true" ? "#10b981" : "#94a3b8" } });
const tone = (s: string) => (s === "done" ? "green" : s === "failed" ? "red" : "amber") as any;

export default function Workflows() {
  const mods = useModules(); const names = Object.keys(mods);
  const [list, setList] = useState<any[]>([]); const [wf, setWf] = useState<any>(null);
  const [nodes, setNodes] = useState<Node[]>([]); const [edges, setEdges] = useState<Edge[]>([]); const [sel, setSel] = useState<string | null>(null);
  const [groups, setGroups] = useState<string[]>([]); const [users, setUsers] = useState<any[]>([]); const [runs, setRuns] = useState<any[]>([]); const [versions, setVersions] = useState<any[]>([]);
  const cf = useCustomFields(wf?.modules?.[0] && wf.modules[0] !== "*" ? wf.modules[0] : "incident");
  const fieldOpts = [...STD, ...cf.map((f) => f.key)];
  const history = (id: number) => { api.get(`/workflows/${id}/runs`).then((r) => setRuns(r.data)); api.get(`/workflows/${id}/versions`).then((r) => setVersions(r.data)); };
  const open = (w: any) => { setWf(w); setNodes(w.nodes.map((n: any, i: number) => ({ ...n, position: n.position || { x: i * 230, y: 80 } }))); setEdges(w.edges.map(deco)); setSel(null); if (w.id) history(w.id); else { setRuns([]); setVersions([]); } };
  const load = (pick?: number) => api.get("/workflows").then((r) => { setList(r.data); const w = r.data.find((x: any) => x.id === pick) || r.data[0]; if (w) open(w); });
  useEffect(() => { load(); api.get("/groups").then((r) => setGroups(r.data.map((g: any) => g.name))); api.get("/users").then((r) => setUsers(r.data.filter((u: any) => u.role !== "end_user"))); }, []);
  const onNodesChange = useCallback((c: NodeChange[]) => setNodes((n) => applyNodeChanges(c, n)), []);
  const onEdgesChange = useCallback((c: EdgeChange[]) => setEdges((e) => applyEdgeChanges(c, e)), []);
  const onConnect = useCallback((c: Connection) => setEdges((e) => addEdge(deco(c), e)), []);
  const add = (type: string) => { const id = `${type[0]}${Date.now() % 100000}`; setNodes((n) => [...n, { id, type, position: { x: 140 + n.length * 50, y: 260 }, data: type === "condition" ? { field: "priority", op: "eq", value: "P1" } : { action: "add_comment", text: "" } }]); setSel(id); };
  const selN = nodes.find((n) => n.id === sel); const sd: any = selN?.data || {};
  const setD = (k: string, v: any) => setNodes((ns) => ns.map((n) => (n.id === sel ? { ...n, data: { ...n.data, [k]: v } } : n)));
  const save = async () => { try { const body = { ...wf, nodes: nodes.map(({ id, type, position, data }) => ({ id, type, position, data })), edges: edges.map(({ id, source, target, sourceHandle }) => ({ id, source, target, sourceHandle })) };
    const r = wf.id ? await api.put(`/workflows/${wf.id}`, body) : await api.post("/workflows", body); toast.success(`Saved as version ${r.data.version}`); load(r.data.id); } catch (x) { toast.error("Couldn't save", { description: errMsg(x) }); } };
  const fresh = () => open({ id: null, name: "New workflow", modules: ["incident"], trigger: "created", trigger_cfg: {}, active: true, nodes: [{ id: "t", type: "trigger", position: { x: 0, y: 100 }, data: { label: "When this happens" } }], edges: [] });
  const cfg = wf?.trigger_cfg || {}; const setCfg = (k: string, v: any) => setWf({ ...wf, trigger_cfg: { ...cfg, [k]: v } });
  const toggleMod = (m: string) => { const cur: string[] = wf.modules || []; setWf({ ...wf, modules: m === "*" ? (cur.includes("*") ? ["incident"] : ["*"]) : cur.includes(m) ? cur.filter((x) => x !== m) : [...cur.filter((x) => x !== "*"), m] }); };
  const FieldSel = ({ v, on }: { v: string; on: (x: string) => void }) => <NativeSelect value={v || ""} onChange={(e) => on(e.target.value)}><option value="">Pick a field…</option>{fieldOpts.map((f) => <option key={f} value={f}>{cf.find((c) => c.key === f)?.label || humanize(f)}{cf.find((c) => c.key === f) ? " (custom)" : ""}</option>)}</NativeSelect>;
  return (
    <Page title="Workflow builder" icon={GitBranch} subtitle="Automate work across one module, several, or all of them. Every save keeps a version; every run is logged."
      actions={<><Button variant="outline" onClick={fresh}><Plus />New workflow</Button><Button onClick={save} disabled={!wf}><Save />Save</Button></>}>
      <div className="flex flex-wrap gap-2">{list.map((w) => <button key={w.id} onClick={() => open(w)} className={cn("flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm", wf?.id === w.id ? "border-primary bg-primary/5 text-primary" : "bg-card")}>
        <span className={cn("size-2 rounded-full", w.active ? "bg-emerald-500" : "bg-slate-300")} />{w.name}<span className="text-xs text-muted-foreground">v{w.version} · {w.runs} runs</span></button>)}</div>
      {wf && <div className="grid gap-4 lg:grid-cols-4">
        <div className="space-y-4 lg:col-span-3">
          <Card className="h-[500px] overflow-hidden"><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} onNodeClick={(_, n) => setSel(n.id)} fitView proOptions={{ hideAttribution: true }}><Background /><Controls /></ReactFlow></Card>
          {wf.id && <Card><Tabs defaultValue="runs"><CardHeader><TabsList><TabsTrigger value="runs"><History className="me-1 size-3.5" />Run history</TabsTrigger><TabsTrigger value="versions">Versions</TabsTrigger></TabsList></CardHeader>
            <TabsContent value="runs" className="px-5 pb-5">{!runs.length ? <p className="text-sm text-muted-foreground">No runs yet. It will run the next time its trigger fires.</p> :
              <div className="divide-y rounded-lg border text-sm">{runs.map((r) => <details key={r.id} className="px-3 py-2"><summary className="flex cursor-pointer items-center gap-3"><Badge tone={tone(r.status)}>{humanize(r.status)}</Badge>
                <span className="font-mono text-xs">{r.record || "—"}</span><span className="text-xs text-muted-foreground">{humanize(r.event)} · v{r.version} · {fmt(r.created_at)}</span></summary>
                <ol className="mt-2 space-y-1 text-xs">{r.trace.map((t: any, i: number) => <li key={i} className="flex gap-2"><span className="font-mono text-muted-foreground">{t.node}</span><span>{t.type}</span>
                  <span className={t.error ? "text-[#E5002B]" : ""}>{t.error || t.did || (t.result === undefined ? "" : t.result ? "→ yes" : "→ no")}</span></li>)}</ol></details>)}</div>}</TabsContent>
            <TabsContent value="versions" className="px-5 pb-5"><div className="divide-y rounded-lg border text-sm">{versions.map((v) => <div key={v.version} className="flex items-center gap-3 px-3 py-2">
              <Badge tone={v.version === wf.version ? "violet" : "neutral"}>v{v.version}</Badge><span className="flex-1 text-xs text-muted-foreground">{fmt(v.created_at)} · {v.snapshot.nodes?.length} steps · {humanize(v.snapshot.trigger)}</span>
              {v.version !== wf.version && <Button size="sm" variant="outline" onClick={async () => { const r = await api.post(`/workflows/${wf.id}/restore/${v.version}`); toast.success(`Restored v${v.version} as v${r.data.version}`); load(wf.id); }}><RotateCcw />Restore</Button>}</div>)}</div></TabsContent></Tabs></Card>}
        </div>
        <div className="space-y-4">
          <Card><CardHeader><CardTitle>Workflow</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
            <div><Label>Name</Label><Input aria-label="Name" value={wf.name} onChange={(e) => setWf({ ...wf, name: e.target.value })} /></div>
            <div><Label>Runs on</Label><div className="flex flex-wrap gap-1.5"><button type="button" onClick={() => toggleMod("*")} className={cn("rounded-full border px-2.5 py-1 text-xs", wf.modules?.includes("*") && "border-primary bg-primary/10 text-primary")}>All modules</button>
              {!wf.modules?.includes("*") && names.map((m) => <button type="button" key={m} onClick={() => toggleMod(m)} className={cn("rounded-full border px-2.5 py-1 text-xs", wf.modules?.includes(m) ? "border-primary bg-primary/10 text-primary" : "text-muted-foreground")}>{mods[m].label}</button>)}</div></div>
            <div><Label>When</Label><NativeSelect aria-label="When" value={wf.trigger} onChange={(e) => setWf({ ...wf, trigger: e.target.value })}>{TRIGGERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</NativeSelect></div>
            {wf.trigger === "state_changed" && <div><Label>To state (optional)</Label><Input aria-label="To state (optional)" value={cfg.to_state || ""} onChange={(e) => setCfg("to_state", e.target.value)} placeholder="e.g. resolved" /></div>}
            {wf.trigger === "schedule" && <div><Label>Every (minutes)</Label><Input aria-label="Every (minutes)" type="number" value={cfg.every_minutes || 60} onChange={(e) => setCfg("every_minutes", +e.target.value)} /></div>}
            {wf.trigger !== "created" && wf.trigger !== "updated" && wf.trigger !== "state_changed" && <div className="space-y-2"><Label>{wf.trigger === "field_changed" ? "Field" : "Only when (optional)"}</Label>
              <FieldSel v={cfg.field} on={(x) => setCfg("field", x)} />
              {cfg.field && wf.trigger !== "field_changed" && <div className="flex gap-2"><NativeSelect value={cfg.op || "eq"} onChange={(e) => setCfg("op", e.target.value)}>{OPS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</NativeSelect><Input value={cfg.value || ""} onChange={(e) => setCfg("value", e.target.value)} placeholder="value" /></div>}</div>}
            <label className="flex items-center justify-between"><span>Enabled</span><Switch checked={wf.active} onCheckedChange={(v) => setWf({ ...wf, active: v })} /></label>
            {wf.id && <div className="flex gap-2"><Button size="sm" variant="outline" onClick={async () => { const r = await api.post(`/workflows/${wf.id}/toggle`); toast.success(r.data.active ? "Enabled" : "Disabled"); load(wf.id); }}><Power />{wf.active ? "Disable" : "Enable"}</Button>
              <Button size="sm" variant="outline" onClick={async () => { const r = await api.post("/workflows/tick"); toast.success(`Resumed ${r.data.resumed}, scheduled ${r.data.scheduled}`); history(wf.id); }}><Play />Run due now</Button>
              <Button size="sm" variant="ghost" aria-label="Delete workflow" onClick={async () => { if (!confirm("Delete this workflow and its history?")) return; await api.delete(`/workflows/${wf.id}`); setWf(null); load(); }}><Trash2 /></Button></div>}
          </CardContent></Card>
          <Card><CardHeader><CardTitle>Add a step</CardTitle></CardHeader><CardContent className="flex gap-2"><Button size="sm" variant="outline" onClick={() => add("condition")}>◆ Condition</Button><Button size="sm" variant="outline" onClick={() => add("action")}>▶ Action</Button></CardContent>
            <p className="px-5 pb-4 text-xs text-muted-foreground">Drag from a step's dot to connect. Conditions and approvals have a green (yes) and red (no) exit.</p></Card>
          {selN && selN.type !== "trigger" && <Card><CardHeader><CardTitle>Edit {selN.type}</CardTitle></CardHeader><CardContent className="space-y-2 text-sm">
            <div><Label>Label</Label><Input aria-label="Label" value={sd.label || ""} onChange={(e) => setD("label", e.target.value)} /></div>
            {selN.type === "condition" ? <><div><Label>Field</Label><FieldSel v={sd.field} on={(x) => setD("field", x)} /></div>
              <div><Label>Operator</Label><NativeSelect aria-label="Operator" value={sd.op} onChange={(e) => setD("op", e.target.value)}>{OPS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</NativeSelect></div>
              <div><Label>Value</Label><Input aria-label="Value" value={sd.value ?? ""} onChange={(e) => setD("value", e.target.value)} /></div></>
              : <><div><Label>Action</Label><NativeSelect aria-label="Action" value={sd.action} onChange={(e) => setD("action", e.target.value)}>{ACTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</NativeSelect></div>
                {sd.action === "set_field" && <><div><Label>Field</Label><FieldSel v={sd.field} on={(x) => setD("field", x)} /></div><div><Label>Value</Label><Input aria-label="Value" value={sd.value ?? ""} onChange={(e) => setD("value", e.target.value)} /></div></>}
                {(sd.action === "assign" || (sd.action === "notify" && (sd.to || "group") === "group")) && <div><Label>Group</Label><NativeSelect aria-label="Group" value={sd.group || ""} onChange={(e) => setD("group", e.target.value)}><option value="">—</option>{groups.map((g) => <option key={g}>{g}</option>)}</NativeSelect></div>}
                {sd.action === "notify" && <div><Label>Who</Label><NativeSelect aria-label="Who" value={sd.to || "group"} onChange={(e) => setD("to", e.target.value)}><option value="group">A group</option><option value="requester">The requester</option><option value="user">A person</option></NativeSelect></div>}
                {(sd.action === "assign" || sd.action === "approval" || (sd.action === "notify" && sd.to === "user")) && <div><Label>{sd.action === "approval" ? "Approver" : "Person"}</Label><NativeSelect value={sd[sd.action === "approval" ? "approver_id" : "user_id"] || ""} onChange={(e) => setD(sd.action === "approval" ? "approver_id" : "user_id", e.target.value ? +e.target.value : null)}><option value="">—</option>{users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</NativeSelect></div>}
                {sd.action === "create_record" && <><div><Label>In module</Label><NativeSelect aria-label="In module" value={sd.module || ""} onChange={(e) => setD("module", e.target.value)}><option value="">Pick…</option>{names.map((m) => <option key={m} value={m}>{mods[m].label}</option>)}</NativeSelect></div>
                  <div><Label>Title</Label><Input aria-label="Title" value={sd.title || ""} onChange={(e) => setD("title", e.target.value)} placeholder="Follow-up for {number}" /></div></>}
                {sd.action === "webhook" && <div><Label>URL</Label><Input aria-label="URL" value={sd.url || ""} onChange={(e) => setD("url", e.target.value)} placeholder="https://…" /></div>}
                {sd.action === "wait" && <div><Label>Minutes</Label><Input aria-label="Minutes" type="number" value={sd.minutes ?? 5} onChange={(e) => setD("minutes", +e.target.value)} /></div>}
                {sd.action === "connector" && <div><Label>Connector</Label><NativeSelect aria-label="Connector" value={sd.kind || ""} onChange={(e) => setD("kind", e.target.value)}>{["teams", "slack", "chatbot", "sla_assist", "pmo", "quality_audit", "webhook"].map((k) => <option key={k}>{k}</option>)}</NativeSelect></div>}
                {["add_comment", "notify", "create_record"].includes(sd.action) && <div><Label>Message</Label><Textarea aria-label="Message" rows={2} value={sd.text || ""} onChange={(e) => setD("text", e.target.value)} placeholder="Use {number}, {title}, {priority}" /></div>}</>}
            <Button size="sm" variant="ghost" className="text-[#E5002B]" onClick={() => { setNodes((n) => n.filter((x) => x.id !== sel)); setEdges((e) => e.filter((x) => x.source !== sel && x.target !== sel)); setSel(null); }}><Trash2 />Remove step</Button>
          </CardContent></Card>}
        </div></div>}
    </Page>
  );
}
