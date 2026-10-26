import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Bookmark, LayoutList, Radio, Trash2 } from "lucide-react";
import { api, errMsg, type Group, type User } from "../api";
import { useAuth } from "../auth";
import { Page, fmt } from "../ui";
import { useLive } from "../hooks/useLive";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";

const MODS = [["incident", "Incidents", "/incidents"], ["request", "Service requests", "/requests"], ["problem", "Problems", "/problems"], ["change", "Changes", "/changes"]];
type F = { state?: string; priority?: string; q?: string; mine?: boolean; unassigned?: boolean };
export default function Workbench() {
  const { user } = useAuth();
  const [module, setModule] = useState("incident"); const [rows, setRows] = useState<any[]>([]); const [f, setF] = useState<F>({});
  const [sel, setSel] = useState<Set<number>>(new Set()); const [views, setViews] = useState<any[]>([]); const [users, setUsers] = useState<User[]>([]); const [groups, setGroups] = useState<Group[]>([]);
  const [live, setLive] = useState(0); const [viewName, setViewName] = useState("");
  const load = () => api.get(`/records/${module}`, { params: { state: f.state || undefined, priority: f.priority || undefined, q: f.q || undefined, mine: f.mine || undefined, limit: 300 } }).then((r) => setRows(r.data));
  useEffect(() => { load(); setSel(new Set()); }, [module, f.state, f.priority, f.mine]);
  useEffect(() => { api.get("/views").then((r) => setViews(r.data)); api.get("/users").then((r) => setUsers(r.data.filter((u: User) => u.role !== "end_user"))); api.get("/groups").then((r) => setGroups(r.data)); }, []);
  useLive((e) => { if (e.module === module) { setLive((n) => n + 1); load(); } });
  const shown = useMemo(() => rows.filter((r) => !f.unassigned || !r.assignee_id), [rows, f.unassigned]);
  const states = useMemo(() => [...new Set(rows.map((r) => r.state))].sort(), [rows]);
  const bulk = async (body: any) => { try { const r = await api.post(`/records/${module}/bulk`, { ids: [...sel], ...body }); toast.success(`Updated ${r.data.updated.length} ticket${r.data.updated.length === 1 ? "" : "s"}`, { description: r.data.skipped.length ? `${r.data.skipped.length} skipped: ${r.data.skipped.map((s: any) => `${s.number} (${s.reason})`).join(", ")}` : undefined }); setSel(new Set()); load(); } catch (x) { toast.error(errMsg(x)); } };
  const route = MODS.find((m) => m[0] === module)![2];
  const all = shown.length > 0 && shown.every((r) => sel.has(r.id));
  return <Page title="Ticket workbench" icon={LayoutList} subtitle="Filter, save views and update many tickets at once. The list refreshes live." wide
    actions={<span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"><Radio className="size-3.5 text-emerald-500" />Live{live > 0 && ` · ${live} update${live === 1 ? "" : "s"}`}</span>}>
    <div className="flex flex-wrap items-center gap-2">
      {views.map((v) => <span key={v.id} className="inline-flex items-center gap-1 rounded-full border bg-card ps-3 text-sm shadow-xs"><button onClick={() => { setModule(v.module); setF(v.filters); }} className="flex items-center gap-1.5 py-1"><Bookmark className="size-3.5 text-primary" />{v.name}</button>
        <button aria-label={`Delete ${v.name}`} className="rounded-full p-1.5 text-muted-foreground hover:text-red-600" onClick={async () => setViews((await api.delete(`/views/${v.id}`)).data)}><Trash2 className="size-3" /></button></span>)}
      {views.length === 0 && <span className="text-sm text-muted-foreground">No saved views yet. Set some filters and save them below.</span>}
    </div>
    <Card className="flex flex-wrap items-end gap-2 p-3">
      <NativeSelect aria-label="Module" className="w-44" value={module} onChange={(e) => { setModule(e.target.value); setF({}); }}>{MODS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</NativeSelect>
      <NativeSelect aria-label="State" className="w-40" value={f.state || ""} onChange={(e) => setF({ ...f, state: e.target.value || undefined })}><option value="">Any state</option>{states.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}</NativeSelect>
      <NativeSelect aria-label="Priority" className="w-36" value={f.priority || ""} onChange={(e) => setF({ ...f, priority: e.target.value || undefined })}><option value="">Any priority</option>{["P1", "P2", "P3", "P4"].map((p) => <option key={p}>{p}</option>)}</NativeSelect>
      <form onSubmit={(e) => { e.preventDefault(); load(); }}><Input aria-label="Search" placeholder="Search…" value={f.q || ""} onChange={(e) => setF({ ...f, q: e.target.value })} className="w-56" /></form>
      <label className="flex items-center gap-1.5 text-sm"><input type="checkbox" checked={!!f.mine} onChange={(e) => setF({ ...f, mine: e.target.checked })} />Assigned to me</label>
      <label className="flex items-center gap-1.5 text-sm"><input type="checkbox" checked={!!f.unassigned} onChange={(e) => setF({ ...f, unassigned: e.target.checked })} />Unassigned</label>
      <div className="flex-1" />
      <form className="flex gap-2" onSubmit={async (e) => { e.preventDefault(); try { setViews((await api.post("/views", { name: viewName, module, filters: f })).data); setViewName(""); toast.success("View saved"); } catch (x) { toast.error(errMsg(x)); } }}>
        <Input aria-label="View name" placeholder="Name this view" value={viewName} onChange={(e) => setViewName(e.target.value)} className="w-44" /><Button size="sm" variant="outline" disabled={!viewName.trim()}><Bookmark />Save view</Button></form>
    </Card>
    {sel.size > 0 && <Card className="sticky top-16 z-10 flex flex-wrap items-center gap-2 border-primary/40 bg-accent p-3 text-sm">
      <b>{sel.size} selected</b>
      <NativeSelect aria-label="Set priority" className="h-8 w-36" value="" onChange={(e) => e.target.value && bulk({ priority: e.target.value })}><option value="">Set priority…</option>{["P1", "P2", "P3", "P4"].map((p) => <option key={p}>{p}</option>)}</NativeSelect>
      <NativeSelect aria-label="Assign to" className="h-8 w-44" value="" onChange={(e) => e.target.value && bulk({ assignee_id: +e.target.value })}><option value="">Assign to…</option>{users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</NativeSelect>
      <NativeSelect aria-label="Set group" className="h-8 w-44" value="" onChange={(e) => e.target.value && bulk({ assignment_group_id: +e.target.value })}><option value="">Set group…</option>{groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</NativeSelect>
      <NativeSelect aria-label="Move to state" className="h-8 w-44" value="" onChange={(e) => e.target.value && bulk({ state: e.target.value })}><option value="">Move to…</option>{["in_progress", "on_hold", "resolved", "closed"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</NativeSelect>
      <Button size="sm" variant="ghost" onClick={() => setSel(new Set())}>Clear</Button>
    </Card>}
    <Card className="overflow-hidden"><table className="w-full"><thead><tr><th className="th w-10"><input type="checkbox" aria-label="Select all" checked={all} onChange={() => setSel(all ? new Set() : new Set(shown.map((r) => r.id)))} /></th>{["Number", "Title", "State", "Priority", "Assignee", "Updated"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
      <tbody>{shown.map((r) => <tr key={r.id} className={sel.has(r.id) ? "bg-accent/50" : ""}><td className="td"><input type="checkbox" aria-label={`Select ${r.number}`} checked={sel.has(r.id)} onChange={() => { const n = new Set(sel); n.has(r.id) ? n.delete(r.id) : n.add(r.id); setSel(n); }} /></td>
        <td className="td"><Link className="font-mono text-xs text-primary" to={`${route}/${r.id}`}>{r.number}</Link></td><td className="td max-w-[420px] truncate">{r.title}{r.data?.spam && <Badge tone="red" className="ms-2">spam</Badge>}</td>
        <td className="td capitalize">{r.state.replace(/_/g, " ")}</td><td className="td"><Badge tone={r.priority === "P1" ? "red" : r.priority === "P2" ? "orange" : "neutral"}>{r.priority}</Badge></td>
        <td className="td">{r.assignee?.full_name || <span className="text-muted-foreground">Unassigned</span>}</td><td className="td whitespace-nowrap text-xs text-muted-foreground">{fmt(r.updated_at || r.created_at)}</td></tr>)}
        {shown.length === 0 && <tr><td colSpan={7} className="td py-10 text-center text-muted-foreground">Nothing matches these filters.{user ? "" : ""}</td></tr>}</tbody></table></Card>
  </Page>;
}
