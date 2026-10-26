import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, ShoppingBag, Star, Trash2 } from "lucide-react";
import { api, errMsg } from "../api";
import { Page } from "../ui";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, NativeSelect, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/misc";
import { cn } from "@/lib/utils";

const TYPES = ["text", "textarea", "number", "date", "choice", "checkbox", "user"];
const blank = () => ({ name: "", category: "General", description: "", requires_approval: true, fulfillment_group: "", form_fields: [], approval_stages: [], fulfilment_tasks: [], entitled: [], active: true });
const norm = (i: any) => ({ ...i, fulfillment_group: i.fulfillment_group || "", form_fields: (i.form_fields || []).map((f: any) => ({ ...f, key: f.key || f.name, type: f.type === "select" ? "choice" : f.type || "text", options: f.options || [] })) });

export default function CatalogAdmin() {
  const [items, setItems] = useState<any[]>([]); const [e, setE] = useState<any>(null); const [groups, setGroups] = useState<any[]>([]); const [users, setUsers] = useState<any[]>([]); const [cs, setCs] = useState<any>(null);
  const load = () => api.get("/catalog-admin/items").then((r) => setItems(r.data));
  useEffect(() => { load(); api.get("/groups").then((r) => setGroups(r.data)); api.get("/users").then((r) => setUsers(r.data.filter((u: any) => u.role !== "end_user"))); api.get("/csat/summary").then((r) => setCs(r.data)); }, []);
  const set = (k: string, v: any) => setE({ ...e, [k]: v });
  const upd = (k: string, idx: number, patch: any) => set(k, e[k].map((x: any, j: number) => j === idx ? (typeof x === "string" ? patch : { ...x, ...patch }) : x));
  const del = (k: string, idx: number) => set(k, e[k].filter((_: any, j: number) => j !== idx));
  const save = async () => { try { const b = { ...e, fulfillment_group: e.fulfillment_group || null };
    const { data } = e.id ? await api.put(`/catalog-admin/items/${e.id}`, b) : await api.post("/catalog-admin/items", b); toast.success("Catalog item saved"); setE(norm(data)); load(); } catch (x) { toast.error(errMsg(x)); } };
  const ENT = ["end_user", "agent", "admin", ...groups.map((g) => `group:${g.name}`)];
  return (
    <Page title="Catalog builder" icon={ShoppingBag} subtitle="Design request forms, approval steps and fulfilment tasks. No code needed."
      actions={<Button onClick={() => setE(blank())}><Plus />New item</Button>}>
      {cs && <Card><CardContent className="flex flex-wrap items-center gap-6 pt-5 text-sm"><div className="flex items-center gap-2"><Star className="size-5 fill-amber-400 text-amber-400" /><span className="text-2xl font-semibold">{cs.average ?? "–"}</span><span className="text-muted-foreground">avg satisfaction</span></div>
        <div><b>{cs.responses}</b> <span className="text-muted-foreground">ratings</span></div><div><b>{cs.satisfied_pct ?? "–"}%</b> <span className="text-muted-foreground">satisfied (4–5)</span></div>
        <div className="flex items-end gap-1">{[1, 2, 3, 4, 5].map((n) => { const v = cs.distribution[String(n)]; const m = Math.max(1, ...Object.values(cs.distribution) as number[]); return <div key={n} className="flex flex-col items-center text-[10px] text-muted-foreground"><div className="w-5 rounded-t bg-primary/70" style={{ height: 4 + 36 * v / m }} />{n}★</div>; })}</div></CardContent></Card>}
      <div className="grid gap-5 lg:grid-cols-[300px_1fr]">
        <Card><CardContent className="space-y-1 p-2">{items.map((i) => <button key={i.id} onClick={() => setE(norm(i))} className={cn("flex w-full items-center justify-between rounded-md px-3 py-2 text-start text-sm hover:bg-accent", e?.id === i.id && "bg-accent")}>
          <span><span className="font-medium">{i.name}</span><span className="block text-xs text-muted-foreground">{i.category} · {i.approval_stages.length || (i.requires_approval ? 1 : 0)} approval step(s)</span></span>{!i.active && <Badge tone="amber">Off</Badge>}</button>)}</CardContent></Card>
        {!e ? <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">Pick an item to edit, or create a new one.</CardContent></Card> : <div className="space-y-4">
          <Card><CardHeader><CardTitle>Basics</CardTitle></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2">
            <div><Label>Name</Label><Input aria-label="Name" value={e.name} onChange={(x) => set("name", x.target.value)} /></div>
            <div><Label>Category</Label><Input aria-label="Category" value={e.category} onChange={(x) => set("category", x.target.value)} /></div>
            <div className="sm:col-span-2"><Label>Description</Label><Textarea aria-label="Description" rows={2} value={e.description} onChange={(x) => set("description", x.target.value)} /></div>
            <div><Label>Fulfilment group</Label><NativeSelect aria-label="Fulfilment group" value={e.fulfillment_group} onChange={(x) => set("fulfillment_group", x.target.value)}><option value="">None</option>{groups.map((g) => <option key={g.id}>{g.name}</option>)}</NativeSelect></div>
            <div className="flex items-center gap-4 pt-6"><label className="flex items-center gap-2 text-sm"><Switch checked={e.requires_approval} onCheckedChange={(v: boolean) => set("requires_approval", v)} />Needs approval</label><label className="flex items-center gap-2 text-sm"><Switch checked={e.active} onCheckedChange={(v: boolean) => set("active", v)} />Active</label></div>
            <div className="sm:col-span-2"><Label>Who can request it (empty = everyone)</Label><div className="mt-1 flex flex-wrap gap-1.5">{ENT.map((t) => { const on = e.entitled.includes(t); return <button key={t} onClick={() => set("entitled", on ? e.entitled.filter((x: string) => x !== t) : [...e.entitled, t])} className={cn("rounded-full border px-2.5 py-0.5 text-xs", on ? "border-primary bg-primary text-primary-foreground" : "text-muted-foreground")}>{t.replace("_", " ")}</button>; })}</div></div>
          </CardContent></Card>
          <Card><CardHeader className="flex-row items-center justify-between"><CardTitle>Form fields</CardTitle><Button size="sm" variant="outline" onClick={() => set("form_fields", [...e.form_fields, { key: `field_${e.form_fields.length + 1}`, label: "New field", type: "text", options: [], required: false }])}><Plus />Field</Button></CardHeader>
            <CardContent className="space-y-2">{!e.form_fields.length && <p className="text-sm text-muted-foreground">No fields yet. Requesters will only add a justification.</p>}
              {e.form_fields.map((f: any, i: number) => <div key={i} className="grid items-end gap-2 rounded-lg border p-3 sm:grid-cols-[1fr_1fr_120px_1fr_auto]">
                <div><Label>Label</Label><Input aria-label="Label" value={f.label} onChange={(x) => upd("form_fields", i, { label: x.target.value })} /></div>
                <div><Label>Key</Label><Input aria-label="Key" value={f.key} onChange={(x) => upd("form_fields", i, { key: x.target.value })} /></div>
                <div><Label>Type</Label><NativeSelect aria-label="Type" value={f.type} onChange={(x) => upd("form_fields", i, { type: x.target.value })}>{TYPES.map((t) => <option key={t}>{t}</option>)}</NativeSelect></div>
                <div><Label>Options (comma separated)</Label><Input aria-label="Options (comma separated)" disabled={f.type !== "choice"} value={(f.options || []).join(", ")} onChange={(x) => upd("form_fields", i, { options: x.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} /></div>
                <Button size="sm" variant="ghost" aria-label="Remove field" onClick={() => del("form_fields", i)}><Trash2 /></Button>
                <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={!!f.required} onChange={(x) => upd("form_fields", i, { required: x.target.checked })} />Required</label>
                <div className="flex items-center gap-1 text-xs sm:col-span-4">Show only when<NativeSelect className="h-8 w-40" value={f.visible_if?.field || ""} onChange={(x) => upd("form_fields", i, { visible_if: x.target.value ? { field: x.target.value, op: "eq", value: f.visible_if?.value || "" } : null })}><option value="">always</option>{e.form_fields.filter((o: any) => o.key !== f.key).map((o: any) => <option key={o.key} value={o.key}>{o.label}</option>)}</NativeSelect>
                  {f.visible_if?.field && <>equals<Input className="h-8 w-40" value={f.visible_if.value} onChange={(x) => upd("form_fields", i, { visible_if: { ...f.visible_if, value: x.target.value } })} /></>}</div></div>)}</CardContent></Card>
          <Card><CardHeader className="flex-row items-center justify-between"><CardTitle>Approval steps</CardTitle><Button size="sm" variant="outline" onClick={() => set("approval_stages", [...e.approval_stages, { name: `Step ${e.approval_stages.length + 1}`, approver: "admin" }])}><Plus />Step</Button></CardHeader>
            <CardContent className="space-y-2">{!e.approval_stages.length && <p className="text-sm text-muted-foreground">{e.requires_approval ? "One approval by an admin." : "No approval: fulfilment starts straight away."}</p>}
              {e.approval_stages.map((s: any, i: number) => <div key={i} className="flex flex-wrap items-center gap-2"><Badge>{i + 1}</Badge><Input className="w-48" value={s.name} onChange={(x) => upd("approval_stages", i, { name: x.target.value })} />
                <NativeSelect className="w-60" value={s.approver} onChange={(x) => upd("approval_stages", i, { approver: x.target.value })}><option value="admin">Any admin</option>{groups.map((g) => <option key={g.id} value={`group:${g.name}`}>Group: {g.name}</option>)}{users.map((u) => <option key={u.id} value={`user:${u.id}`}>{u.full_name}</option>)}</NativeSelect>
                <Button size="sm" variant="ghost" aria-label="Remove step" onClick={() => del("approval_stages", i)}><Trash2 /></Button></div>)}</CardContent></Card>
          <Card><CardHeader className="flex-row items-center justify-between"><CardTitle>Fulfilment tasks</CardTitle><Button size="sm" variant="outline" onClick={() => set("fulfilment_tasks", [...e.fulfilment_tasks, "New task"])}><Plus />Task</Button></CardHeader>
            <CardContent className="space-y-2">{!e.fulfilment_tasks.length && <p className="text-sm text-muted-foreground">No tasks: the request is fulfilled as soon as it's approved.</p>}
              {e.fulfilment_tasks.map((t: string, i: number) => <div key={i} className="flex items-center gap-2"><Badge>{i + 1}</Badge><Input value={t} onChange={(x) => upd("fulfilment_tasks", i, x.target.value)} /><Button size="sm" variant="ghost" aria-label="Remove task" onClick={() => del("fulfilment_tasks", i)}><Trash2 /></Button></div>)}
              <p className="text-xs text-muted-foreground">When every task is ticked off, the request is marked fulfilled automatically.</p></CardContent></Card>
          <div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setE(null)}>Cancel</Button><Button onClick={save}>Save item</Button></div>
        </div>}
      </div>
    </Page>
  );
}
