import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { ArrowDown, ArrowUp, Eye, EyeOff, LayoutList, Pencil, Plus, Trash2 } from "lucide-react";
import { api, errMsg } from "../api";
import { Page } from "../ui";
import { useModules } from "../modules";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, NativeSelect, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/misc";
import { CustomFieldsForm, type CField } from "@/components/CustomFields";
import { humanize } from "@/lib/utils";

const TYPES: [string, string][] = [["text", "Text"], ["textarea", "Long text"], ["number", "Number"], ["date", "Date"], ["choice", "Choice"], ["multichoice", "Multi-choice"],
  ["user", "User"], ["group", "Group"], ["reference", "Record / CI reference"], ["checkbox", "Checkbox"]];
const blank = (module: string): any => ({ label: "", type: "text", options: [], required: false, default: "", help: "", section: "Details", hidden: false, show_in_list: false, modules: [module], condition: {}, ref_module: null });

export default function FormDesigner() {
  const mods = useModules(); const names = Object.keys(mods);
  const [module, setModule] = useState("incident"); const [all, setAll] = useState<CField[]>([]); const [edit, setEdit] = useState<any>(null); const [preview, setPreview] = useState<Record<string, any>>({});
  const load = () => api.get("/forms/fields").then((r) => setAll(r.data));
  useEffect(() => { load(); }, []);
  const fields = useMemo(() => all.filter((f) => f.modules.includes(module) || f.modules.includes("*")), [all, module]);
  const save = async () => {
    try { const body = { ...edit, options: typeof edit.options === "string" ? edit.options.split(",").map((x: string) => x.trim()).filter(Boolean) : edit.options };
      if (edit.id) await api.put(`/forms/fields/${edit.id}`, body); else await api.post("/forms/fields", body);
      toast.success("Field saved"); setEdit(null); load(); } catch (x) { toast.error("Couldn't save the field", { description: errMsg(x) }); }
  };
  const move = async (i: number, d: number) => { const ids = fields.map((f) => f.id); const j = i + d; if (j < 0 || j >= ids.length) return; [ids[i], ids[j]] = [ids[j], ids[i]];
    await api.post("/forms/fields/reorder", { ids }); load(); };
  const toggle = async (f: CField) => { await api.put(`/forms/fields/${f.id}`, { ...f, hidden: !f.hidden }); load(); };
  const del = async (f: CField) => { if (!confirm(`Remove “${f.label}”? Existing values stay on records.`)) return; await api.delete(`/forms/fields/${f.id}`); toast.success("Field removed"); load(); };
  const others = fields.filter((f) => f.id !== edit?.id);
  return (
    <Page title="Form designer" icon={LayoutList} subtitle="Add your own fields to any module. No code needed: they show up in forms, lists, filters, the API, exports and the audit trail."
      actions={<Button onClick={() => setEdit(blank(module))}><Plus />Add field</Button>}>
      <div className="flex flex-wrap items-center gap-2"><Label className="mb-0">Module</Label>
        <NativeSelect className="w-56" value={module} onChange={(e) => { setModule(e.target.value); setPreview({}); }}>{names.map((m) => <option key={m} value={m}>{mods[m].label}</option>)}</NativeSelect>
        <span className="text-xs text-muted-foreground">{fields.length} custom field{fields.length === 1 ? "" : "s"}</span></div>
      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-3"><CardHeader><CardTitle>Fields</CardTitle></CardHeader><CardContent className="p-0">
          {!fields.length && <p className="p-6 text-sm text-muted-foreground">No custom fields yet. Click “Add field” to create your first one.</p>}
          <div className="divide-y">{fields.map((f, i) => <div key={f.id} className="flex items-center gap-3 px-4 py-3 text-sm" data-testid="field-row">
            <div className="flex flex-col"><button aria-label="Move up" onClick={() => move(i, -1)}><ArrowUp className="size-3.5" /></button><button aria-label="Move down" onClick={() => move(i, 1)}><ArrowDown className="size-3.5" /></button></div>
            <div className="min-w-0 flex-1"><div className="flex items-center gap-2 font-medium">{f.label}{f.required && <span className="text-destructive">*</span>}{f.hidden && <Badge tone="neutral">Hidden</Badge>}</div>
              <div className="mt-0.5 flex flex-wrap gap-1.5 text-xs text-muted-foreground"><span className="font-mono">{f.key}</span>·<span>{TYPES.find((t) => t[0] === f.type)?.[1]}</span>·<span>{f.section}</span>
                {f.modules.length > 1 || f.modules[0] === "*" ? <Badge tone="violet">Shared: {f.modules[0] === "*" ? "all modules" : f.modules.map((m) => mods[m]?.label || m).join(", ")}</Badge> : null}
                {f.condition?.field && <Badge tone="amber">Shown when {humanize(f.condition.field)} {({ neq: `≠ ${f.condition.value}`, filled: "is filled", empty: "is empty" } as any)[f.condition.op || ""] || `= ${f.condition.value}`}</Badge>}</div></div>
            <Button size="icon" variant="ghost" aria-label="Show or hide" onClick={() => toggle(f)}>{f.hidden ? <EyeOff /> : <Eye />}</Button>
            <Button size="icon" variant="ghost" aria-label="Edit" onClick={() => setEdit({ ...f, options: f.options.join(", ") })}><Pencil /></Button>
            <Button size="icon" variant="ghost" aria-label="Delete" onClick={() => del(f)}><Trash2 /></Button></div>)}</div>
        </CardContent></Card>
        <div className="space-y-3 lg:col-span-2"><div className="text-xs font-medium text-muted-foreground">Live preview of the {mods[module]?.label || module} form</div>
          <CustomFieldsForm defs={fields.filter((f) => !f.hidden)} values={preview} onChange={setPreview} /></div>
      </div>
      {edit && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={() => setEdit(null)}>
        <div className="max-h-[90vh] w-full max-w-2xl space-y-3 overflow-auto rounded-xl bg-card p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
          <h2 className="font-heading text-lg font-semibold">{edit.id ? "Edit field" : "New field"}</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <div><Label>Label</Label><Input aria-label="Label" value={edit.label} onChange={(e) => setEdit({ ...edit, label: e.target.value })} placeholder="e.g. Asset tag" /></div>
            <div><Label>Type</Label><NativeSelect aria-label="Type" value={edit.type} onChange={(e) => setEdit({ ...edit, type: e.target.value })}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</NativeSelect></div>
            {["choice", "multichoice"].includes(edit.type) && <div className="sm:col-span-2"><Label>Options (comma separated)</Label><Input aria-label="Options (comma separated)" value={edit.options} onChange={(e) => setEdit({ ...edit, options: e.target.value })} placeholder="Laptop, Phone, Tablet" /></div>}
            {edit.type === "reference" && <div><Label>Refers to module</Label><NativeSelect aria-label="Refers to module" value={edit.ref_module || ""} onChange={(e) => setEdit({ ...edit, ref_module: e.target.value || null })}><option value="">Pick…</option>{names.map((m) => <option key={m} value={m}>{mods[m].label}</option>)}</NativeSelect></div>}
            <div><Label>Section</Label><Input aria-label="Section" value={edit.section} onChange={(e) => setEdit({ ...edit, section: e.target.value })} /></div>
            <div><Label>Default value</Label><Input aria-label="Default value" value={edit.default ?? ""} onChange={(e) => setEdit({ ...edit, default: e.target.value })} /></div>
            <div className="sm:col-span-2"><Label>Help text</Label><Textarea aria-label="Help text" rows={2} value={edit.help} onChange={(e) => setEdit({ ...edit, help: e.target.value })} /></div>
            <div className="sm:col-span-2"><Label>Show only when (optional)</Label><div className="flex gap-2">
              <NativeSelect value={edit.condition?.field || ""} onChange={(e) => setEdit({ ...edit, condition: e.target.value ? { ...edit.condition, field: e.target.value, op: edit.condition?.op || "eq" } : {} })}><option value="">Always show</option>{others.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}</NativeSelect>
              {edit.condition?.field && <><NativeSelect className="w-36" value={edit.condition.op} onChange={(e) => setEdit({ ...edit, condition: { ...edit.condition, op: e.target.value } })}><option value="eq">equals</option><option value="neq">is not</option><option value="filled">is filled</option><option value="empty">is empty</option></NativeSelect>
                <Input value={edit.condition.value || ""} onChange={(e) => setEdit({ ...edit, condition: { ...edit.condition, value: e.target.value } })} placeholder="value" /></>}</div></div>
            <div className="sm:col-span-2"><Label>Use on modules</Label><div className="flex flex-wrap gap-1.5">
              <button type="button" onClick={() => setEdit({ ...edit, modules: edit.modules.includes("*") ? [module] : ["*"] })} className={`rounded-full border px-2.5 py-1 text-xs ${edit.modules.includes("*") ? "border-primary bg-primary/10 text-primary" : ""}`}>All modules</button>
              {!edit.modules.includes("*") && names.map((m) => <button type="button" key={m} onClick={() => setEdit({ ...edit, modules: edit.modules.includes(m) ? edit.modules.filter((x: string) => x !== m) : [...edit.modules, m] })}
                className={`rounded-full border px-2.5 py-1 text-xs ${edit.modules.includes(m) ? "border-primary bg-primary/10 text-primary" : "text-muted-foreground"}`}>{mods[m].label}</button>)}</div></div>
            <label className="flex items-center gap-2 text-sm"><Switch checked={edit.required} onCheckedChange={(v) => setEdit({ ...edit, required: v })} />Required</label>
            <label className="flex items-center gap-2 text-sm"><Switch checked={edit.show_in_list} onCheckedChange={(v) => setEdit({ ...edit, show_in_list: v })} />Show as list column &amp; filter</label>
          </div>
          <div className="flex justify-end gap-2 pt-2"><Button variant="outline" onClick={() => setEdit(null)}>Cancel</Button><Button onClick={save}>Save field</Button></div></div></div>}
    </Page>
  );
}
