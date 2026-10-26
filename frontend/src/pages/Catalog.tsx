import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { AppWindow, Check, Cloud, HardDrive, KeyRound, Laptop, Lock, Monitor, Package, Search, Shield, Smartphone, Users, Zap } from "lucide-react";
import { api, errMsg } from "../api";
import { isStaff, useAuth } from "../auth";
import { Page } from "../ui";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input, Label, NativeSelect, Textarea } from "@/components/ui/input";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/menu";
import { EmptyState, Skeleton } from "@/components/ui/misc";
import { cn } from "@/lib/utils";

const TONES = ["bg-indigo-50 text-indigo-600", "bg-sky-50 text-sky-600", "bg-emerald-50 text-emerald-600",
  "bg-amber-50 text-amber-600", "bg-violet-50 text-violet-600", "bg-rose-50 text-rose-600"];
const pick = (c: any) => { const n = `${c.name} ${c.category}`.toLowerCase();
  return /laptop|notebook/.test(n) ? Laptop : /monitor|display/.test(n) ? Monitor : /phone|mobile/.test(n) ? Smartphone : /vpn|access|permission/.test(n) ? Lock : /licen|key/.test(n) ? KeyRound
    : /cloud|aws|azure/.test(n) ? Cloud : /software|app|install/.test(n) ? AppWindow : /security|mfa/.test(n) ? Shield : /onboard|account|user|hr/.test(n) ? Users : /storage|disk|drive/.test(n) ? HardDrive : Package; };
export const CatalogIcon = ({ c, size = "md" }: { c: any; size?: "md" | "lg" }) => { const I = pick(c); const tone = TONES[[...(c.category || "")].reduce((a: number, ch: string) => a + ch.charCodeAt(0), 0) % TONES.length];
  return <div className={cn("flex shrink-0 items-center justify-center rounded-lg", tone, size === "lg" ? "size-11" : "size-9")}><I className={size === "lg" ? "size-5" : "size-[18px]"} /></div>; };

export default function Catalog() {
  const [items, setItems] = useState<any[] | null>(null); const [sel, setSel] = useState<any>(null); const [vals, setVals] = useState<any>({}); const [just, setJust] = useState(""); const [q, setQ] = useState(""); const [cat, setCat] = useState(""); const [busy, setBusy] = useState(false);
  const { user } = useAuth(); const staff = isStaff(user); const [people, setPeople] = useState<any[]>([]); const [obo, setObo] = useState("");
  const fk = (f: any) => f.key || f.name;
  const vis = (f: any) => { const c = f.visible_if || {}; if (!c.field) return true; const v = String(vals[c.field] ?? "").toLowerCase(), x = String(c.value ?? "").toLowerCase(); return c.op === "neq" ? v !== x : v === x; };
  const nav = useNavigate();
  useEffect(() => { api.get("/portal/catalog").then((r) => setItems(r.data)); if (staff) api.get("/users").then((r) => setPeople(r.data)); }, [staff]);
  const order = async () => {
    const missing = (sel.form_fields || []).filter((f: any) => vis(f) && f.required && !vals[fk(f)]).map((f: any) => f.label);
    if (missing.length) { toast.error("Please complete required fields", { description: missing.join(", ") }); return; }
    setBusy(true); try { const { data } = await api.post(`/portal/order/${sel.id}`, { values: vals, justification: just, on_behalf_of: obo ? +obo : null }); toast.success(`Request ${data.number} submitted`, { description: sel.requires_approval ? "Sent for approval" : "Fulfilment has started" }); nav(`/requests/${data.id}`); }
    catch (x) { toast.error(errMsg(x)); } finally { setBusy(false); } };
  const cats = [...new Set((items || []).map((i) => i.category))];
  const shown = (items || []).filter((i) => (!cat || i.category === cat) && (!q || `${i.name} ${i.description}`.toLowerCase().includes(q.toLowerCase())));
  return (
    <Page title="Service Catalog" icon={Package} subtitle="Request hardware, software, access and services. Most items are fulfilled automatically.">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-sm"><Search className="pointer-events-none absolute start-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><Input className="ps-8" placeholder="Search the catalog…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <div className="flex flex-wrap gap-1 rounded-lg border bg-card p-1 shadow-xs">{["", ...cats].map((c) => <button key={c || "all"} onClick={() => setCat(c)} className={cn("rounded-md px-3 py-1 text-xs font-medium transition-colors", cat === c ? "bg-primary text-primary-foreground shadow-xs" : "text-muted-foreground hover:bg-accent hover:text-foreground")}>{c || "All"}</button>)}</div>
      </div>
      {items === null ? <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[...Array(8)].map((_, i) => <Skeleton key={i} className="h-40" />)}</div> : !shown.length ? <EmptyState icon={Search} title="No catalog items match" desc="Try a different search or category." /> :
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{shown.map((i) => (
          <button key={i.id} onClick={() => { setSel(i); setVals({}); setJust(""); setObo(""); }} className="group flex flex-col rounded-xl border bg-card p-5 text-start shadow-xs transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-soft">
            <div className="flex items-start justify-between"><CatalogIcon c={i} size="lg" /><Badge tone={i.requires_approval ? "amber" : "green"}>{i.requires_approval ? <><Lock className="size-3" />Approval</> : <><Zap className="size-3" />Instant</>}</Badge></div>
            <div className="mt-4 font-medium">{i.name}</div><div className="mt-1 line-clamp-2 flex-1 text-sm text-muted-foreground">{i.description}</div>
            <div className="mt-4 flex items-center justify-between border-t pt-3 text-xs text-muted-foreground"><span>{i.category}</span><span className="font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">Request →</span></div></button>))}</div>}
      <Dialog open={!!sel} onOpenChange={(o) => !o && setSel(null)}>
        <DialogContent className="max-w-lg">{sel && <>
          <div className="flex items-start gap-3 border-b p-5"><CatalogIcon c={sel} size="lg" /><div className="pe-6"><DialogTitle className="text-base font-semibold">{sel.name}</DialogTitle><p className="mt-0.5 text-sm text-muted-foreground">{sel.description}</p></div></div>
          <div className="space-y-4 p-5">
            {staff && <div><Label>Requested for</Label><NativeSelect aria-label="Requested for" value={obo} onChange={(e) => setObo(e.target.value)}><option value="">Myself</option>{people.filter((p) => p.id !== user?.id).map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}</NativeSelect></div>}
            {sel.form_fields.filter(vis).map((f: any) => <div key={fk(f)}><Label>{f.label}{f.required && <span className="text-destructive"> *</span>}</Label>
              {["select", "choice"].includes(f.type) ? <NativeSelect value={vals[fk(f)] || ""} onChange={(e) => setVals({ ...vals, [fk(f)]: e.target.value })}><option value="">Select…</option>{f.options.map((o: string) => <option key={o}>{o}</option>)}</NativeSelect>
                : f.type === "textarea" ? <Textarea rows={2} value={vals[fk(f)] || ""} onChange={(e) => setVals({ ...vals, [fk(f)]: e.target.value })} />
                : f.type === "checkbox" ? <input type="checkbox" checked={!!vals[fk(f)]} onChange={(e) => setVals({ ...vals, [fk(f)]: e.target.checked })} />
                : <Input type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"} value={vals[fk(f)] || ""} onChange={(e) => setVals({ ...vals, [fk(f)]: e.target.value })} />}
              {f.help && <p className="mt-1 text-xs text-muted-foreground">{f.help}</p>}</div>)}
            <div><Label>Business justification</Label><Textarea aria-label="Business justification" rows={3} value={just} onChange={(e) => setJust(e.target.value)} placeholder="Why do you need this?" /></div>
            <div className="flex items-center gap-2 rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground">{sel.requires_approval ? <><Lock className="size-3.5" />{(sel.approval_stages || []).length > 1 ? `${sel.approval_stages.length} approval steps: ${sel.approval_stages.map((s: any) => s.name || "Approval").join(" → ")}.` : "Someone will be asked to approve this request."}</> : <><Check className="size-3.5 text-emerald-600" />Fulfilled automatically once submitted.</>}</div>
          </div>
          <div className="flex justify-end gap-2 border-t bg-muted/30 px-5 py-3"><Button variant="outline" onClick={() => setSel(null)}>Cancel</Button><Button onClick={order} disabled={busy}>{busy ? "Submitting…" : "Submit request"}</Button></div></>}
        </DialogContent></Dialog>
    </Page>
  );
}
