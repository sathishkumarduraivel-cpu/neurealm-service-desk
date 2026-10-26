import { useT } from "@/i18n";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import type { ColumnDef } from "@tanstack/react-table";
import { AlertTriangle, ArrowLeft, BookPlus, CheckCircle2, ChevronRight, Clock, FileText, GitMerge, Link2, ListChecks, MessageSquare, MoreHorizontal, Plus, Send, ShoppingBag, Sparkles, UserCheck, XCircle } from "lucide-react";
import { api, errMsg, type Group, type Rec, type User } from "../api";
import { isStaff, useAuth } from "../auth";
import { AiPanel, Page, Priority, Sla, State, fmt } from "../ui";
import { pathFor, useModules, type Field } from "../modules";
import { titleFor } from "../nav";
import { DataTable } from "@/components/DataTable";
import { TicketTools, ConflictDialog } from "@/components/TicketTools";
import { useLive } from "../hooks/useLive";
import { CustomFieldsCard, CustomFieldsForm, CustomValue, useCustomFields } from "@/components/CustomFields";
import { Download } from "lucide-react";
import { Attachments } from "@/components/Attachments";
import { RequesterFeedback } from "@/components/Feedback";
import { ItsmPanels } from "@/components/ItsmPanels";
import { TicketAI } from "@/components/NeurealmAI";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FieldError, Input, Label, NativeSelect, Textarea } from "@/components/ui/input";
import { Avatar, Person, Skeleton, Switch, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/misc";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/menu";
import { cn, humanize, relTime } from "@/lib/utils";

const CORE = ["incident", "problem", "change", "request"];
export const ROUTE = new Proxy({} as Record<string, string>, { get: (_t, m: string) => pathFor(m).slice(1) });
const COMPUTED_SKIP = new Set(["escalation_level", "values", "catalog_item_id", "incident_ids", "pending_playbook", "dq_missing"]);
const iconFor = (m: string) => titleFor(pathFor(m))?.icon || FileText;

export function FieldInput({ f, value, onChange }: { f: Field; value: any; onChange: (v: any) => void }) {
  if (f.type === "select") return <NativeSelect value={value ?? ""} onChange={(e) => onChange(e.target.value)}><option value="">Select…</option>{f.options!.map((o) => <option key={o} value={o}>{humanize(o)}</option>)}</NativeSelect>;
  if (f.type === "bool") return <div className="flex h-9 items-center"><Switch checked={!!value} onCheckedChange={(v) => onChange(v)} /></div>;
  if (f.type === "textarea") return <Textarea value={value ?? ""} onChange={(e) => onChange(e.target.value)} />;
  return <Input type={f.type} value={value ?? ""} onChange={(e) => onChange(f.type === "number" ? (e.target.value === "" ? "" : +e.target.value) : e.target.value)} />;
}
const show = (v: any) => (typeof v === "boolean" ? (v ? "Yes" : "No") : Array.isArray(v) ? v.join(", ") : v === "" || v == null ? "—" : String(v));
const ShowVal = ({ v, f }: { v: any; f?: Field }) => {
  if (typeof v === "boolean") return <Badge tone={v ? "green" : "neutral"}>{v ? "Yes" : "No"}</Badge>;
  if (f?.type === "select" && v) return <span className="capitalize">{humanize(String(v))}</span>;
  return <span className={cn(show(v) === "—" && "text-muted-foreground")}>{show(v)}</span>;
};

export function RecordList({ module }: { module: string }) {
  const { user } = useAuth(); const nav = useNavigate(); const mods = useModules(); const meta = mods[module]; const core = CORE.includes(module); const { t } = useT();
  const extra = core ? [] : (meta?.fields || []).filter((f) => f.type !== "textarea").slice(0, 3);
  const cdefs = useCustomFields(module);
  const [rows, setRows] = useState<Rec[] | null>(null);
  const load = (q?: string) => api.get(`/records/${module}`, { params: { q: q || undefined, limit: 500 } }).then((r) => setRows(r.data)).catch((e) => { toast.error(errMsg(e)); setRows([]); });
  useEffect(() => { setRows(null); load(); }, [module]);
  const canCreate = !!user && !!meta?.create.includes(user.role);
  const label = t(meta?.label || humanize(module)); const Icon = iconFor(module);
  const flat = useMemo(() => (rows || []).map((r) => ({ ...r, _group: r.assignment_group?.name || "", _assignee: r.assignee?.full_name || "" })), [rows]);
  const cols = useMemo<ColumnDef<any>[]>(() => [
    { accessorKey: "number", header: "Number", size: 120, enableHiding: false, cell: ({ row }) => <Link onClick={(e) => e.stopPropagation()} className="font-mono text-xs font-medium text-primary hover:underline" to={`/${ROUTE[module]}/${row.original.id}`}>{row.original.number}</Link> },
    { accessorKey: "title", header: "Title", enableHiding: false, cell: ({ row: { original: r } }) => <div className="min-w-[200px] max-w-[320px]"><div className="truncate font-medium">{r.title}</div>
      <div className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">{r.category && <span className="capitalize">{r.category}</span>}{r.requester && <><span>·</span><span>{r.requester.full_name}</span></>}
        {r.data?.known_error && <Badge tone="violet" className="ms-1">Known error</Badge>}</div></div> },
    { accessorKey: "priority", header: "Priority", size: 90, cell: ({ getValue }: any) => <Priority p={getValue()} /> },
    { accessorKey: "state", header: "State", size: 130, cell: ({ getValue }: any) => <State s={getValue()} /> },
    ...(core ? [
      ...(module === "change" ? [{ id: "risk", header: "Type / Risk", accessorFn: (r: any) => r.data?.risk_score, cell: ({ row: { original: r } }: any) => <span className="flex items-center gap-1.5 text-xs"><span className="capitalize">{r.data.change_type}</span>
        <Badge tone={r.data.risk_level === "high" ? "red" : r.data.risk_level === "moderate" ? "amber" : "green"} className="tabular-nums">{r.data.risk_score} · {r.data.risk_level}</Badge></span> } as ColumnDef<any>] : []),
      { accessorKey: "_group", header: "Group", cell: ({ getValue }: any) => <span className="block max-w-[150px] truncate text-muted-foreground" title={getValue()}>{getValue() || "—"}</span> },
      { accessorKey: "_assignee", header: "Assignee", cell: ({ getValue }: any) => <Person name={getValue()} /> },
    ] as ColumnDef<any>[] : extra.map((f) => ({ id: f.name, header: f.label, accessorFn: (r: any) => r.data?.[f.name], cell: ({ getValue }: any) => <span className="whitespace-nowrap"><ShowVal v={getValue()} f={f} /></span> }) as ColumnDef<any>)),
    ...cdefs.filter((f) => f.show_in_list).map((f) => ({ id: `cf_${f.key}`, header: f.label, accessorFn: (r: any) => { const v = r.data?.[f.key]; return Array.isArray(v) ? v.join(", ") : v ?? ""; },
      cell: ({ row: { original: r } }: any) => <span className="whitespace-nowrap"><CustomValue f={f} v={r.data?.[f.key]} /></span> }) as ColumnDef<any>),
    { accessorKey: "sla_status", header: "SLA", size: 100, cell: ({ getValue }: any) => <Sla s={getValue()} /> },
    { accessorKey: "created_at", header: "Created", size: 110, cell: ({ getValue }: any) => <span className="whitespace-nowrap text-xs text-muted-foreground" title={fmt(getValue())}>{relTime(getValue())}</span> },
  ], [module, meta, cdefs, t]);
  const open = (rows || []).filter((r) => !/(resolved|closed|cancel|done|complete|retired)/.test(r.state));
  return (
    <Page title={user?.role === "end_user" ? `My ${label}` : label} icon={Icon} subtitle={rows ? t("{n} records · {o} open", { n: rows.length, o: open.length }) : t("Loading…")} actions={<>
      {module === "request" && <Button variant="outline" asChild><Link to="/catalog"><ShoppingBag />Order from catalog</Link></Button>}
      {user && user.role !== "end_user" && <Button variant="outline" onClick={async () => { const r = await api.get(`/records/${module}/export.csv`, { responseType: "blob" }); const a = document.createElement("a"); a.href = URL.createObjectURL(r.data); a.download = `${module}s.csv`; a.click(); }}><Download />{t("Export")}</Button>}
      {canCreate && <Button asChild><Link to={`/${ROUTE[module]}/new`}><Plus />{module === "incident" ? t("New incident") : `New ${label.replace(/s$/, "").toLowerCase()}`}</Link></Button>}</>}>
      {core && rows && rows.length > 0 && <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[[t("Open"), open.length, "text-foreground"], [t("Critical (P1)"), open.filter((r) => r.priority === "P1").length, "text-red-600"],
          [t("SLA breached"), open.filter((r) => r.sla_breached).length, "text-red-600"], [t("Unassigned"), open.filter((r) => !r.assignee).length, "text-amber-600"]].map(([l, v, c]) =>
          <div key={l as string} className="flex items-center justify-between rounded-lg border bg-card px-4 py-3 shadow-xs"><span className="text-xs font-medium text-muted-foreground">{l}</span><span className={cn("text-lg font-semibold tabular-nums", c as string)}>{v}</span></div>)}</div>}
      <DataTable data={flat} columns={cols} loading={rows === null} onRowClick={(r) => nav(`/${ROUTE[module]}/${r.id}`)} searchPlaceholder={t("Search {x}…", { x: label.toLowerCase() })} onSearchSubmit={(q) => load(q)}
        facets={[{ id: "state", label: "State" }, { id: "priority", label: "Priority" }, ...(core ? [{ id: "_group", label: "Group" }] : []), ...cdefs.filter((f) => f.show_in_list && ["choice", "checkbox"].includes(f.type)).map((f) => ({ id: `cf_${f.key}`, label: f.label }))]} />
    </Page>
  );
}

const schema = z.object({ title: z.string().trim().min(5, "Please describe the issue in at least 5 characters").max(200, "Keep it under 200 characters"), description: z.string().max(5000).optional(),
  impact: z.string().optional(), urgency: z.string().optional(), change_type: z.string().optional(), rollback_plan: z.string().optional(), tested: z.boolean().optional() });
type FormV = z.infer<typeof schema>;

export function IncidentCreate({ module = "incident" }: { module?: string }) {
  const { user } = useAuth(); const nav = useNavigate(); const staff = isStaff(user); const meta = useModules()[module];
  const cdefs = useCustomFields(module); const [qs] = useSearchParams();
  const [dv, setDv] = useState<any>({}); const [ai, setAi] = useState<any>(null); const [aiLoading, setAiLoading] = useState(false);
  const { register, handleSubmit, watch, setValue, formState: { errors, isSubmitting } } = useForm<FormV>({ resolver: zodResolver(schema), defaultValues: { title: (qs.get("title") || "").slice(0, 200), description: qs.get("description") || "", impact: "", urgency: "", change_type: "normal", rollback_plan: "", tested: false } });
  const title = watch("title"), description = watch("description"), tested = watch("tested");
  useEffect(() => {
    if ((title || "").length < 4 || (meta && !meta.ai)) { setAi(null); return; }
    setAiLoading(true); const t = setTimeout(() => api.post("/ai/triage", { title, description }).then((r) => setAi(r.data)).finally(() => setAiLoading(false)), 400);
    return () => clearTimeout(t);
  }, [title, description]);
  const submit = async (f: FormV) => {
    const body: any = { title: f.title, description: f.description, use_ai: true, data: {} };
    if (f.impact) body.impact = +f.impact; if (f.urgency) body.urgency = +f.urgency;
    if (module === "change") body.data = { ...dv, change_type: f.change_type, rollback_plan: f.rollback_plan, tested: f.tested, affects_production: true }; else body.data = dv;
    try { const { data } = await api.post(`/records/${module}`, body); toast.success(`${data.number} created`, { description: data.assignment_group ? `Routed to ${data.assignment_group.name}` : undefined }); nav(`/${ROUTE[module]}/${data.id}`); }
    catch (x) { toast.error("Could not create record", { description: errMsg(x) }); }
  };
  const label = (meta?.label || humanize(module)).replace(/s$/, "");
  return (
    <Page title={`New ${label.toLowerCase()}`} icon={iconFor(module)} subtitle={staff ? "Create a record. AI fills in category, priority and routing for you." : "Tell us what's wrong. We'll route it to the right team automatically."}
      actions={<Button variant="ghost" onClick={() => nav(-1)}><ArrowLeft />Back</Button>}>
      <div className="grid gap-5 lg:grid-cols-5">
        <form onSubmit={handleSubmit(submit)} className="space-y-5 lg:col-span-3">
          <Card><CardHeader><CardTitle>Details</CardTitle></CardHeader><CardContent className="space-y-4">
            <div><Label>Short description <span className="text-destructive">*</span></Label><Input {...register("title")} placeholder="e.g. VPN down for all users in Chennai office" aria-invalid={!!errors.title} className={cn(errors.title && "border-destructive focus-visible:ring-destructive/30")} /><FieldError msg={errors.title?.message} /></div>
            <div><Label>Description</Label><Textarea aria-label="Description" rows={6} {...register("description")} placeholder="What happened? When did it start? Who is affected?" /></div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div><Label>Impact</Label><NativeSelect aria-label="Impact" {...register("impact")}><option value="">Let AI decide</option><option value="1">1 · High</option><option value="2">2 · Medium</option><option value="3">3 · Low</option></NativeSelect></div>
              <div><Label>Urgency</Label><NativeSelect aria-label="Urgency" {...register("urgency")}><option value="">Let AI decide</option><option value="1">1 · High</option><option value="2">2 · Medium</option><option value="3">3 · Low</option></NativeSelect></div>
            </div></CardContent></Card>
          {module === "change" && <Card><CardHeader><CardTitle>Change plan</CardTitle></CardHeader><CardContent className="grid gap-4 sm:grid-cols-2">
            <div><Label>Change type</Label><NativeSelect aria-label="Change type" {...register("change_type")}><option value="standard">Standard</option><option value="normal">Normal</option><option value="emergency">Emergency</option></NativeSelect></div>
            <div><Label>Rollback plan</Label><Input aria-label="Rollback plan" {...register("rollback_plan")} placeholder="How will you revert?" /></div>
            <label className="flex items-center gap-3 text-sm sm:col-span-2"><Switch checked={!!tested} onCheckedChange={(v) => setValue("tested", v)} />Tested in staging</label></CardContent></Card>}
          {module !== "change" && !!meta?.fields.length && <Card><CardHeader><CardTitle>{label} fields</CardTitle></CardHeader><CardContent className="grid gap-4 sm:grid-cols-2">
            {meta.fields.map((fl) => <div key={fl.name} className={cn(fl.type === "textarea" && "sm:col-span-2")}><Label>{fl.label}</Label><FieldInput f={fl} value={dv[fl.name]} onChange={(v) => setDv({ ...dv, [fl.name]: v })} /></div>)}</CardContent></Card>}
          <CustomFieldsForm defs={cdefs} values={dv} onChange={setDv} />
          <div className="flex items-center justify-end gap-2"><Button type="button" variant="outline" onClick={() => nav(-1)}>Cancel</Button><Button disabled={isSubmitting}><Send />{isSubmitting ? "Submitting…" : "Submit"}</Button></div>
        </form>
        <div className="space-y-4 lg:col-span-2"><div className="lg:sticky lg:top-4 space-y-4">
          {ai ? <AiPanel s={ai} /> : meta?.ai !== false && <div className="rounded-lg border border-dashed border-indigo-200 bg-indigo-50/40 p-5">
            <div className="flex items-center gap-2 text-sm font-medium"><Sparkles className={cn("size-4 text-indigo-500", aiLoading && "animate-pulse")} />{aiLoading ? "Analysing…" : "Neurealm AI is ready"}</div>
            <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">Start typing a short description. AI suggests the category, priority, assignment group and matching knowledge articles in real time.</p></div>}
        </div></div>
      </div>
    </Page>
  );
}

type TL = { at: string; kind: "created" | "comment" | "resolved" | "approval"; who?: string | null; body?: string; meta?: string };
function Timeline({ items }: { items: TL[] }) {
  const ic = { created: [Plus, "bg-sky-100 text-sky-600"], comment: [MessageSquare, "bg-muted text-muted-foreground"], resolved: [CheckCircle2, "bg-emerald-100 text-emerald-600"], approval: [UserCheck, "bg-amber-100 text-amber-700"] } as const;
  return <ol className="relative space-y-5 before:absolute before:start-[13px] before:top-2 before:h-[calc(100%-16px)] before:w-px before:bg-border">
    {items.map((it, i) => { const [I, c] = ic[it.kind]; return <li key={i} className="relative flex gap-3">
      <span className={cn("relative z-10 flex size-7 shrink-0 items-center justify-center rounded-full ring-4 ring-card", c)}><I className="size-3.5" /></span>
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="flex flex-wrap items-center gap-x-1.5 text-sm">{it.who && <span className="font-medium">{it.who}</span>}<span className="text-muted-foreground">{it.meta}</span><span className="text-xs text-muted-foreground/80">· {relTime(it.at)}</span></div>
        {it.body && <div className="mt-1.5 whitespace-pre-wrap rounded-lg border bg-muted/30 px-3 py-2 text-sm">{it.body}</div>}</div></li>; })}
  </ol>;
}
const Prop = ({ label, children }: { label: string; children: React.ReactNode }) => <label className="grid grid-cols-[110px_1fr] items-center gap-2 py-1.5 text-sm"><span className="text-xs text-muted-foreground">{label}</span><div className="min-w-0">{children}</div></label>;

export function RecordDetail({ module }: { module: string }) {
  const { t } = useT();
  const { id } = useParams(); const { user } = useAuth(); const staff = isStaff(user); const meta = useModules()[module]; const nav = useNavigate();
  const [edit, setEdit] = useState<any>(null);
  const [r, setR] = useState<Rec | null>(null); const [groups, setGroups] = useState<Group[]>([]); const [users, setUsers] = useState<User[]>([]);
  const [note, setNote] = useState(""); const [wa, setWa] = useState(""); const [link, setLink] = useState("");
  const load = () => api.get(`/records/${module}/${id}`).then((x) => setR(x.data)).catch((e) => toast.error(errMsg(e)));
  useEffect(() => { load(); if (staff) { api.get("/groups").then((x) => setGroups(x.data)); api.get("/users").then((x) => setUsers(x.data.filter((u: User) => u.role !== "end_user"))); } }, [id]);
  const cdefs = useCustomFields(module);
  const [conflict, setConflict] = useState(false); const { user: me } = useAuth();
  const patch = async (body: any, msg = "Saved") => { try { setR((await api.patch(`/records/${module}/${id}`, { ...body, expected_updated_at: r?.updated_at })).data); toast.success(msg); } catch (x: any) { if (x?.response?.status === 409) setConflict(true); else toast.error("Update failed", { description: errMsg(x) }); } };
  useLive((e) => { if (e.id === Number(id) && e.by_id !== me?.id) toast.info(`${e.by || "Someone"} just updated ${e.number}`, { action: { label: "Refresh", onClick: () => load() } }); });
  const comment = async () => { if (!note.trim()) return; await api.post(`/records/${module}/${id}/comments`, { body: note }); setNote(""); load(); toast.success("Comment posted"); };
  const decide = async (aid: number, approve: boolean) => { try { setR((await api.post(`/approvals/${aid}/decide`, { approve })).data); toast.success(approve ? "Approved" : "Rejected"); } catch (x) { toast.error(errMsg(x)); } };
  if (!r) return <div className="mx-auto max-w-[1440px] space-y-5 px-6 py-6"><Skeleton className="h-5 w-40" /><Skeleton className="h-8 w-[480px]" /><div className="grid gap-5 lg:grid-cols-3"><Skeleton className="h-96 lg:col-span-2" /><Skeleton className="h-96" /></div></div>;
  const timeline: TL[] = [{ at: r.created_at, kind: "created" as const, who: r.requester?.full_name, meta: `created ${r.number}` },
    ...(r.comments || []).map((c: any) => ({ at: c.created_at, kind: "comment" as const, who: c.author?.full_name, meta: c.internal ? "added a work note" : "commented", body: c.body })),
    ...(r.approvals || []).filter((a: any) => a.decided_at).map((a: any) => ({ at: a.decided_at, kind: "approval" as const, who: a.approver?.full_name, meta: `${a.state} level ${a.level} approval` })),
    ...(r.resolved_at ? [{ at: r.resolved_at, kind: "resolved" as const, meta: "Record resolved" }] : [])].sort((a, b) => a.at.localeCompare(b.at));
  const extraData = meta ? Object.entries(r.data || {}).filter(([k]) => !meta.fields.find((f) => f.name === k) && !cdefs.find((f) => f.key === k) && !COMPUTED_SKIP.has(k)) : [];
  const related = r.linked || []; const approvals = r.approvals || [];
  const hasDetails = module === "change" || module === "problem" || module === "request" || (!CORE.includes(module) && !!meta);
  const listLabel = meta?.label || humanize(module); const Icon = iconFor(module);
  const trans = staff ? r.allowed_transitions || [] : [];
  const dueMs = r.sla_due_at ? new Date(r.sla_due_at + "Z").getTime() : 0; const totalMs = dueMs ? dueMs - new Date(r.created_at + "Z").getTime() : 0;
  const slaPct = totalMs > 0 ? Math.min(100, Math.max(0, (100 * (Date.now() - new Date(r.created_at + "Z").getTime())) / totalMs)) : 0;
  return (
    <div className="mx-auto w-full max-w-[1440px] space-y-5 px-6 py-6">
      <div>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground"><Link to={`/${ROUTE[module]}`} className="inline-flex items-center gap-1.5 hover:text-foreground"><Icon className="size-3.5" />{listLabel}</Link><ChevronRight className="size-3" /><span className="font-mono">{r.number}</span></div>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0"><h1 className="text-xl font-semibold tracking-tight">{r.title}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-2"><State s={r.state} /><Priority p={r.priority} label /><Sla s={r.sla_status} />{r.data?.known_error && <Badge tone="violet">Known error</Badge>}
              <span className="text-xs text-muted-foreground">Opened {relTime(r.created_at)} by {r.requester?.full_name || "system"}</span></div></div>
          <div className="flex flex-wrap items-center gap-2">
            {trans.slice(0, 3).map((s, i) => <Button key={s} variant={i === 0 ? "default" : "outline"} size="sm" onClick={() => patch({ state: s }, `Moved to ${humanize(s)}`)}>{/(resol|close|complete|done)/.test(s) ? <CheckCircle2 /> : /(cancel|reject)/.test(s) ? <XCircle /> : <ChevronRight />}{humanize(s).replace(/^./, (c) => c.toUpperCase())}</Button>)}
            {(trans.length > 3 || (staff && module === "incident")) && <DropdownMenu><DropdownMenuTrigger asChild><Button variant="outline" size="icon-sm" aria-label={t("More actions")}><MoreHorizontal /></Button></DropdownMenuTrigger><DropdownMenuContent align="end">
              {trans.slice(3).map((s) => <DropdownMenuItem key={s} onSelect={() => patch({ state: s }, `Moved to ${humanize(s)}`)}><ChevronRight /><span className="capitalize">{humanize(s)}</span></DropdownMenuItem>)}
              {staff && module === "incident" && <DropdownMenuItem disabled={!["resolved", "closed"].includes(r.state)} onSelect={async () => { const a = (await api.post(`/kb/from-incident/${id}`)).data; toast.success(`Draft ${a.number} created`, { action: { label: "Open", onClick: () => nav(`/knowledge/${a.id}`) } }); }}><BookPlus />Generate KB article</DropdownMenuItem>}
            </DropdownMenuContent></DropdownMenu>}
          </div>
        </div>
      </div>
      <div className="grid gap-5 lg:grid-cols-3">
        <div className="min-w-0 space-y-5 lg:col-span-2">
          <Card><CardHeader><CardTitle>Description</CardTitle></CardHeader><CardContent><p className="whitespace-pre-wrap text-sm leading-relaxed">{r.description || <span className="text-muted-foreground">No description provided.</span>}</p></CardContent></Card>
          <ItsmPanels r={r} module={module} staff={staff} onChange={load} />
          <Card className="p-0"><Tabs defaultValue="activity"><div className="px-5 pt-2"><TabsList className="border-b-0">
            <TabsTrigger value="activity"><MessageSquare />Activity<Badge className="ms-0.5 px-1">{timeline.length}</Badge></TabsTrigger>
            {hasDetails && <TabsTrigger value="details"><ListChecks />Details</TabsTrigger>}
            <TabsTrigger value="related"><Link2 />Related<Badge className="ms-0.5 px-1">{related.length}</Badge></TabsTrigger>
            {approvals.length > 0 && <TabsTrigger value="approvals"><UserCheck />Approvals<Badge className="ms-0.5 px-1">{approvals.length}</Badge></TabsTrigger>}
          </TabsList></div><div className="border-t" />
            <TabsContent value="activity" className="px-5 pb-5"><Timeline items={timeline} />
              <div className="mt-5 flex gap-3"><Avatar name={user?.full_name} size={28} /><div className="flex-1 rounded-lg border bg-card focus-within:ring-2 focus-within:ring-ring/30">
                <textarea className="block min-h-[72px] w-full resize-none rounded-t-lg bg-transparent px-3 py-2 text-sm outline-none placeholder:text-muted-foreground" placeholder={staff ? "Add a comment or work note…" : "Add a comment…"} value={note} onChange={(e) => setNote(e.target.value)} onKeyDown={(e) => (e.metaKey || e.ctrlKey) && e.key === "Enter" && comment()} />
                <div className="flex items-center justify-between border-t px-2 py-1.5"><span className="px-1 text-[11px] text-muted-foreground">⌘ + Enter to post</span><Button size="sm" onClick={comment} disabled={!note.trim()}>Post</Button></div></div></div>
            </TabsContent>
            {hasDetails && <TabsContent value="details" className="space-y-4 px-5 pb-5">
              {module === "change" && <dl className="grid gap-3 sm:grid-cols-4">{[["Type", <span className="capitalize">{r.data.change_type}</span>], ["Risk", <Badge tone={r.data.risk_level === "high" ? "red" : r.data.risk_level === "moderate" ? "amber" : "green"}>{r.data.risk_score} · {r.data.risk_level}</Badge>],
                ["Rollback plan", r.data.rollback_plan || <span className="text-red-600">Missing</span>], ["Tested", <ShowVal v={!!r.data.tested} />]].map(([l, v], i) => <div key={i} className="rounded-lg border bg-muted/20 p-3"><dt className="text-xs text-muted-foreground">{l}</dt><dd className="mt-1 text-sm font-medium">{v}</dd></div>)}</dl>}
              {module === "problem" && <div className="space-y-4 text-sm">
                <div className="grid gap-3 sm:grid-cols-2"><div className="rounded-lg border bg-muted/20 p-3"><div className="text-xs text-muted-foreground">Root cause</div><div className="mt-1">{r.data.root_cause || "—"}</div></div>
                  <div className="rounded-lg border bg-muted/20 p-3"><div className="text-xs text-muted-foreground">Known error / workaround</div><div className="mt-1">{r.data.known_error ? <span className="text-violet-700">{r.data.workaround}</span> : "Not a known error yet"}</div></div></div>
                {staff && !r.data.known_error && <div className="flex gap-2"><Input placeholder="Describe the workaround" value={wa} onChange={(e) => setWa(e.target.value)} /><Button onClick={async () => { setR((await api.post(`/records/problem/${id}/known-error`, { workaround: wa })).data); toast.success("Marked as known error"); }}><AlertTriangle />Mark known error</Button></div>}
              </div>}
              {module === "request" && <div className="space-y-2 text-sm"><Prop label="Catalog item">{r.data.item}</Prop>{r.data.values && <dl className="grid gap-2 sm:grid-cols-3">{Object.entries(r.data.values).map(([k, v]) => <div key={k} className="rounded-lg border bg-muted/20 p-3"><dt className="text-xs capitalize text-muted-foreground">{humanize(k)}</dt><dd className="mt-1 font-medium">{show(v)}</dd></div>)}</dl>}</div>}
              {!CORE.includes(module) && meta && <div>
                <div className="mb-3 flex items-center justify-between"><span className="text-xs font-medium text-muted-foreground">{meta.label} attributes</span>{staff && (edit ? <div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => setEdit(null)}>Cancel</Button><Button size="sm" onClick={async () => { await patch({ data: edit }); setEdit(null); }}>Save changes</Button></div> : <Button size="sm" variant="outline" onClick={() => setEdit({ ...r.data })}>Edit</Button>)}</div>
                <dl className="grid gap-3 sm:grid-cols-3">{meta.fields.map((fl) => <div key={fl.name} className={cn("rounded-lg border p-3", edit ? "bg-card" : "bg-muted/20")}><dt className="mb-1 text-xs text-muted-foreground">{fl.label}</dt><dd className="text-sm font-medium">{edit ? <FieldInput f={fl} value={edit[fl.name]} onChange={(v) => setEdit({ ...edit, [fl.name]: v })} /> : <ShowVal v={r.data[fl.name]} f={fl} />}</dd></div>)}</dl>
                {extraData.length > 0 && <div className="mt-4 rounded-lg border border-indigo-200/70 bg-indigo-50/40 p-3"><div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-indigo-700"><Sparkles className="size-3.5" />Computed by Neurealm Service Desk</div>
                  <div className="flex flex-wrap gap-2">{extraData.map(([k, v]) => <span key={k} className="rounded-md border bg-card px-2 py-1 text-xs"><span className="capitalize text-muted-foreground">{humanize(k)}</span> <b className="font-medium">{show(v)}</b></span>)}</div></div>}
                {r.data.dq_missing?.length > 0 && <div className="mt-3 flex items-center gap-2 text-xs text-amber-700"><AlertTriangle className="size-3.5" />Missing for data quality: {r.data.dq_missing.join(", ")}</div>}
              </div>}
            </TabsContent>}
            <TabsContent value="related" className="px-5 pb-5">
              {related.length ? <div className="divide-y rounded-lg border">{related.map((l) => { const I = iconFor(l.module); return <Link key={l.id} to={`${pathFor(l.module)}/${l.id}`} className="flex items-center gap-3 px-3 py-2.5 text-sm hover:bg-muted/40">
                <I className="size-4 text-muted-foreground" /><span className="w-28 font-mono text-xs text-primary">{l.number}</span><span className="flex-1 truncate">{l.title}</span><State s={l.state} /></Link>; })}</div>
                : <div className="rounded-lg border border-dashed py-8 text-center text-sm text-muted-foreground"><GitMerge className="mx-auto mb-2 size-5" />No related records</div>}
              {staff && module === "problem" && <div className="mt-3 flex gap-2"><Input className="max-w-[200px]" placeholder="Incident ID" value={link} onChange={(e) => setLink(e.target.value)} /><Button variant="outline" onClick={async () => { setR((await api.post(`/records/problem/${id}/link/${link}`)).data); setLink(""); toast.success("Incident linked"); }}><Link2 />Link incident</Button></div>}
            </TabsContent>
            {approvals.length > 0 && <TabsContent value="approvals" className="px-5 pb-5"><div className="divide-y rounded-lg border">{approvals.map((a: any) => <div key={a.id} className="flex items-center gap-3 px-3 py-2.5 text-sm">
              <span className="flex size-6 items-center justify-center rounded-full bg-muted text-xs font-medium">L{a.level}</span><Person name={a.approver?.full_name} /><span className="flex-1" /><State s={a.state} />
              {a.state === "requested" && staff && <><Button size="sm" onClick={() => decide(a.id, true)}>Approve</Button><Button size="sm" variant="outline" onClick={() => decide(a.id, false)}>Reject</Button></>}</div>)}</div></TabsContent>}
          </Tabs></Card>
        </div>
        <div className="space-y-5">
          <Card><CardHeader><CardTitle>Properties</CardTitle></CardHeader><CardContent className="divide-y">
            <Prop label="Requester"><Person name={r.requester?.full_name} /></Prop>
            <Prop label="Category"><span className="capitalize">{r.category || "—"}</span></Prop>
            <Prop label="Group">{staff ? <NativeSelect className="h-8" value={r.assignment_group_id ?? ""} onChange={(e) => patch({ assignment_group_id: +e.target.value || null }, "Assignment group updated")}><option value="">Unassigned</option>{groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</NativeSelect> : r.assignment_group?.name || "—"}</Prop>
            <Prop label="Assignee">{staff ? <NativeSelect className="h-8" value={r.assignee_id ?? ""} onChange={(e) => patch({ assignee_id: +e.target.value || null }, "Assignee updated")}><option value="">Unassigned</option>{users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</NativeSelect> : <Person name={r.assignee?.full_name} />}</Prop>
            {staff && <Prop label="Impact / Urgency"><div className="grid grid-cols-2 gap-2"><NativeSelect className="h-8" value={r.impact} onChange={(e) => patch({ impact: +e.target.value }, "Impact updated")}>{[1, 2, 3].map((v) => <option key={v} value={v}>{v} · {["High", "Medium", "Low"][v - 1]}</option>)}</NativeSelect>
              <NativeSelect className="h-8" value={r.urgency} onChange={(e) => patch({ urgency: +e.target.value }, "Urgency updated")}>{[1, 2, 3].map((v) => <option key={v} value={v}>{v} · {["High", "Medium", "Low"][v - 1]}</option>)}</NativeSelect></div></Prop>}
            <Prop label="Created">{fmt(r.created_at)}</Prop><Prop label="Resolved">{fmt(r.resolved_at)}</Prop>
          </CardContent></Card>
          {r.sla_due_at && <Card><CardHeader><CardTitle className="flex items-center gap-2"><Clock className="size-4 text-muted-foreground" />Service level</CardTitle><Sla s={r.sla_status} /></CardHeader><CardContent>
            <div className="flex justify-between text-xs text-muted-foreground"><span>Resolution due</span><span className="font-medium text-foreground">{fmt(r.sla_due_at)}</span></div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted"><div className={cn("h-full rounded-full", r.sla_breached ? "bg-red-500" : slaPct > 75 ? "bg-amber-500" : "bg-emerald-500")} style={{ width: `${r.resolved_at ? 100 : slaPct}%` }} /></div>
            <div className="mt-1.5 text-[11px] text-muted-foreground">{r.resolved_at ? "Resolved" : r.sla_breached ? `Breached ${relTime(r.sla_due_at)}` : `Due ${relTime(r.sla_due_at)}`}</div></CardContent></Card>}
          <AiPanel s={r.ai_suggestion} />
          <CustomFieldsCard defs={cdefs} data={r.data || {}} editable={staff} onSave={async (d) => { setR((await api.patch(`/records/${module}/${id}`, { data: d, expected_updated_at: r.updated_at })).data); toast.success("Saved"); }} />
          {staff && <TicketAI module={module} id={r.id} onPosted={load} />}
          <RequesterFeedback r={r} me={me} module={module} onChange={load} />
          <Attachments module={module} id={r.id} staff={staff} />
          <TicketTools module={module} r={r} setR={setR} staff={staff} users={users} reload={load} />
        </div>
        <ConflictDialog open={conflict} onClose={() => setConflict(false)} onReload={() => { setConflict(false); load(); }} />
      </div>
    </div>
  );
}
