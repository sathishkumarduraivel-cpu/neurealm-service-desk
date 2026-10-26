import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Pencil } from "lucide-react";
import { api, errMsg } from "../api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, NativeSelect, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/misc";
import { cn } from "@/lib/utils";

export type CField = { id: number; key: string; label: string; type: string; options: string[]; required: boolean; default: any; help: string; section: string;
  position: number; hidden: boolean; show_in_list: boolean; modules: string[]; condition: { field?: string; op?: string; value?: string }; ref_module?: string | null };

const cache: Record<string, CField[]> = {};
export function useCustomFields(module: string) {
  const [defs, setDefs] = useState<CField[]>(cache[module] || []);
  useEffect(() => { api.get("/forms/fields", { params: { module } }).then((r) => { cache[module] = r.data; setDefs(r.data); }).catch(() => setDefs([])); }, [module]);
  return defs;
}

export function isVisible(f: CField, data: Record<string, any>) {
  const c = f.condition || {}; if (!c.field) return true;
  const v = data[c.field]; const vs = Array.isArray(v) ? v.map((x) => String(x).toLowerCase()) : [String(v ?? "").toLowerCase()]; const x = String(c.value ?? "").toLowerCase();
  if (c.op === "neq") return !vs.includes(x); if (c.op === "filled") return !!v && vs[0] !== ""; if (c.op === "empty") return !v; return vs.includes(x);
}

const people: { users?: Promise<any[]>; groups?: Promise<any[]> } = {};
function useLookup(type: string, refModule?: string | null) {
  const [opts, setOpts] = useState<{ id: number; name: string }[]>([]);
  useEffect(() => {
    if (type === "user") (people.users ||= api.get("/users").then((r) => r.data)).then((u) => setOpts(u.map((x: any) => ({ id: x.id, name: x.full_name })))).catch(() => {});
    if (type === "group") (people.groups ||= api.get("/groups").then((r) => r.data)).then((g) => setOpts(g.map((x: any) => ({ id: x.id, name: x.name })))).catch(() => {});
    if (type === "reference" && refModule) api.get(`/records/${refModule}`, { params: { limit: 200 } }).then((r) => setOpts(r.data.map((x: any) => ({ id: x.id, name: `${x.number} · ${x.title}` })))).catch(() => {});
  }, [type, refModule]);
  return opts;
}

export function CustomInput({ f, value, onChange }: { f: CField; value: any; onChange: (v: any) => void }) {
  const opts = useLookup(f.type, f.ref_module);
  if (f.type === "textarea") return <Textarea value={value ?? ""} onChange={(e) => onChange(e.target.value)} />;
  if (f.type === "checkbox") return <div className="flex h-9 items-center"><Switch checked={!!value} onCheckedChange={onChange} /></div>;
  if (f.type === "choice") return <NativeSelect value={value ?? ""} onChange={(e) => onChange(e.target.value)}><option value="">Select…</option>{f.options.map((o) => <option key={o}>{o}</option>)}</NativeSelect>;
  if (f.type === "multichoice") { const cur: string[] = Array.isArray(value) ? value : [];
    return <div className="flex flex-wrap gap-1.5">{f.options.map((o) => <button type="button" key={o} onClick={() => onChange(cur.includes(o) ? cur.filter((x) => x !== o) : [...cur, o])}
      className={cn("rounded-full border px-2.5 py-1 text-xs", cur.includes(o) ? "border-primary bg-primary/10 text-primary" : "bg-card text-muted-foreground")}>{o}</button>)}</div>; }
  if (["user", "group", "reference"].includes(f.type)) return <NativeSelect value={value ?? ""} onChange={(e) => onChange(e.target.value ? +e.target.value : null)}><option value="">Select…</option>{opts.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</NativeSelect>;
  return <Input type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"} value={value ?? ""} onChange={(e) => onChange(f.type === "number" ? (e.target.value === "" ? "" : +e.target.value) : e.target.value)} />;
}

export function CustomValue({ f, v }: { f: CField; v: any }) {
  const opts = useLookup(["user", "group", "reference"].includes(f.type) ? f.type : "", f.ref_module);
  if (v === null || v === undefined || v === "" || (Array.isArray(v) && !v.length)) return <span className="text-muted-foreground">—</span>;
  if (f.type === "checkbox") return <span>{v ? "Yes" : "No"}</span>;
  if (Array.isArray(v)) return <span>{v.join(", ")}</span>;
  if (opts.length) return <span>{opts.find((o) => o.id === v)?.name || `#${v}`}</span>;
  return <span>{String(v)}</span>;
}

const sections = (defs: CField[]) => defs.reduce((m, f) => ((m[f.section || "Details"] ||= []).push(f), m), {} as Record<string, CField[]>);

/** Renders designer-defined fields, grouped by section, honouring conditional visibility. */
export function CustomFieldsForm({ defs, values, onChange }: { defs: CField[]; values: Record<string, any>; onChange: (v: Record<string, any>) => void }) {
  useEffect(() => { const d: Record<string, any> = {}; defs.forEach((f) => { if (values[f.key] === undefined && f.default != null && f.default !== "") d[f.key] = f.default; });
    if (Object.keys(d).length) onChange({ ...values, ...d }); }, [defs.length]);
  if (!defs.length) return null;
  return <>{Object.entries(sections(defs)).map(([s, fs]) => <Card key={s} data-testid="custom-section"><CardHeader><CardTitle>{s}</CardTitle></CardHeader><CardContent className="grid gap-4 sm:grid-cols-2">
    {fs.filter((f) => isVisible(f, values)).map((f) => <div key={f.key} className={cn(f.type === "textarea" && "sm:col-span-2")}>
      <Label>{f.label}{f.required && <span className="text-destructive"> *</span>}</Label><CustomInput f={f} value={values[f.key]} onChange={(v) => onChange({ ...values, [f.key]: v })} />
      {f.help && <p className="mt-1 text-xs text-muted-foreground">{f.help}</p>}</div>)}</CardContent></Card>)}</>;
}

export function CustomFieldsCard({ defs, data, editable, onSave }: { defs: CField[]; data: Record<string, any>; editable: boolean; onSave: (d: Record<string, any>) => Promise<void> }) {
  const [edit, setEdit] = useState<Record<string, any> | null>(null);
  if (!defs.length) return null;
  return <Card><CardHeader className="flex-row items-center justify-between"><CardTitle>Additional fields</CardTitle>
    {editable && (edit ? <div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => setEdit(null)}>Cancel</Button>
      <Button size="sm" onClick={async () => { try { await onSave(edit); setEdit(null); } catch (x) { toast.error(errMsg(x)); } }}>Save</Button></div>
      : <Button size="sm" variant="outline" onClick={() => setEdit({ ...data })}><Pencil />Edit</Button>)}</CardHeader>
    <CardContent className="space-y-4">{Object.entries(sections(defs)).map(([s, fs]) => <div key={s}><div className="mb-2 text-xs font-medium text-muted-foreground">{s}</div>
      <dl className="grid gap-3 sm:grid-cols-2">{fs.filter((f) => isVisible(f, edit || data)).map((f) => <div key={f.key} className="rounded-lg border bg-muted/20 p-3">
        <dt className="mb-1 text-xs text-muted-foreground">{f.label}{edit && f.required && <span className="text-destructive"> *</span>}</dt>
        <dd className="text-sm font-medium">{edit ? <CustomInput f={f} value={edit[f.key]} onChange={(v) => setEdit({ ...edit, [f.key]: v })} /> : <CustomValue f={f} v={data[f.key]} />}</dd></div>)}</dl></div>)}</CardContent></Card>;
}
