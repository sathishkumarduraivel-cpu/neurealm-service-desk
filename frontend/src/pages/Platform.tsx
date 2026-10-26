import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { AlertTriangle, Bell, Code2, DatabaseBackup, Download, Mail, Plus, Server, Trash2, Users } from "lucide-react";
import { api, errMsg } from "../api";
import { Page } from "../ui";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, NativeSelect, Textarea } from "@/components/ui/input";
import { EmptyState, Switch, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/misc";

const err = (x: any) => toast.error(errMsg(x));
async function download(url: string) {
  try { const r = await api.get(url, { responseType: "blob" }); const cd = r.headers["content-disposition"] || ""; const a = document.createElement("a"); a.href = URL.createObjectURL(r.data); a.download = (cd.match(/filename="(.+)"/) || [])[1] || "servicedesk-export"; a.click(); } catch (x) { err(x); }
}

function EmailTab() {
  const [c, setC] = useState<any>(null); const [once, setOnce] = useState("");
  useEffect(() => { api.get("/email/config").then((r) => setC(r.data)); }, []);
  const save = (rotate = false) => api.put("/email/config", { ...c, rotate }).then((r) => { setC(r.data); if (r.data.token_once) setOnce(r.data.token_once); toast.success("Saved"); }).catch(err);
  if (!c) return null;
  const url = `${import.meta.env.VITE_API_URL || location.origin}/api/inbound/email/1?token=${once || "<token>"}`;
  return <div className="grid gap-4 lg:grid-cols-2"><Card><CardHeader><CardTitle>Email to ticket</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
    <label className="flex items-center gap-2"><Switch checked={c.enabled} onCheckedChange={(v: boolean) => setC({ ...c, enabled: v })} />Turn emails into tickets</label>
    <div><Label>Support address (shown to users)</Label><Input aria-label="Support address (shown to users)" value={c.address} onChange={(e) => setC({ ...c, address: e.target.value })} /></div>
    <div><Label>New emails become</Label><NativeSelect aria-label="New emails become" value={c.module} onChange={(e) => setC({ ...c, module: e.target.value })}><option value="incident">Incidents</option><option value="request">Service requests</option></NativeSelect></div>
    <label className="flex items-center gap-2"><Switch checked={c.allow_unknown} onCheckedChange={(v: boolean) => setC({ ...c, allow_unknown: v })} />Accept emails from people who aren't users yet</label>
    <div className="flex gap-2"><Button onClick={() => save()}>Save</Button><Button variant="outline" onClick={() => save(true)}>New token</Button></div></CardContent></Card>
    <Card><CardHeader><CardTitle>How to connect your mailbox</CardTitle></CardHeader><CardContent className="space-y-2 text-sm text-muted-foreground">
      <p>Point your mail relay's inbound webhook (for example SendGrid Inbound Parse, Mailgun Routes or Postmark) to this address. Send JSON with <code>from</code>, <code>subject</code> and <code>text</code>.</p>
      <pre tabIndex={0} className="overflow-x-auto rounded-lg bg-muted p-3 text-xs text-foreground">POST {url}</pre>
      {once ? <p className="text-amber-700">Copy this token now. It won't be shown again.</p> : <p>Token: {c.has_token ? c.token : "not created yet"}</p>}
      <p>Replies that keep the ticket number in the subject, like <code>[INC0001001]</code>, are added to that ticket as comments. Quoted history is trimmed.</p></CardContent></Card></div>;
}

const BLANK = { name: "", source: "", severity: "", contains: "", action: "suppress", set_severity: "critical", enabled: true };
function AlertsTab() {
  const [rs, setRs] = useState<any[]>([]); const [t, setT] = useState({ source: "prometheus", node: "web-01", metric: "disk_full", severity: "warning", message: "" }); const [res, setRes] = useState<any>(null);
  useEffect(() => { api.get("/alerts/rules").then((r) => setRs(r.data)); }, []);
  const save = () => api.put("/alerts/rules", rs).then((r) => { setRs(r.data); toast.success("Rules saved"); }).catch(err);
  const upd = (i: number, k: string, v: any) => setRs(rs.map((r, j) => j === i ? { ...r, [k]: v } : r));
  return <div className="space-y-4"><Card><CardHeader className="flex-row items-center justify-between"><CardTitle>Alert rules</CardTitle><div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => setRs([...rs, { ...BLANK, name: `Rule ${rs.length + 1}` }])}><Plus />Add rule</Button><Button size="sm" onClick={save}>Save</Button></div></CardHeader>
    <CardContent className="space-y-2 text-sm"><p className="text-muted-foreground">Rules run top to bottom on every incoming alert. The first match wins. Alerts that pass are grouped and turned into incidents.</p>
      {rs.map((r, i) => <div key={i} className="grid grid-cols-2 items-end gap-2 rounded-lg border p-3 md:grid-cols-7">
        <div><Label>Name</Label><Input aria-label="Name" value={r.name} onChange={(e) => upd(i, "name", e.target.value)} /></div>
        <div><Label>Source is</Label><Input aria-label="Source is" placeholder="any" value={r.source} onChange={(e) => upd(i, "source", e.target.value)} /></div>
        <div><Label>Severity is</Label><Input aria-label="Severity is" placeholder="any" value={r.severity} onChange={(e) => upd(i, "severity", e.target.value)} /></div>
        <div><Label>Text contains</Label><Input aria-label="Text contains" placeholder="any" value={r.contains} onChange={(e) => upd(i, "contains", e.target.value)} /></div>
        <div><Label>Then</Label><NativeSelect aria-label="Then" value={r.action} onChange={(e) => upd(i, "action", e.target.value)}><option value="suppress">Ignore it</option><option value="set_severity">Change severity</option><option value="create">Keep as is</option></NativeSelect></div>
        <div>{r.action === "set_severity" && <><Label>New severity</Label><NativeSelect aria-label="New severity" value={r.set_severity} onChange={(e) => upd(i, "set_severity", e.target.value)}>{["critical", "major", "minor", "warning", "info"].map((s) => <option key={s}>{s}</option>)}</NativeSelect></>}</div>
        <div className="flex items-center gap-2"><Switch checked={r.enabled} onCheckedChange={(v: boolean) => upd(i, "enabled", v)} /><Button size="sm" variant="ghost" aria-label="Delete rule" onClick={() => setRs(rs.filter((_, j) => j !== i))}><Trash2 /></Button></div></div>)}
      {!rs.length && <EmptyState icon={Bell} title="No rules yet" desc="Every alert is kept. Add a rule to ignore noise or raise severity." />}</CardContent></Card>
    <Card><CardHeader><CardTitle>Try a sample alert</CardTitle></CardHeader><CardContent className="flex flex-wrap items-end gap-2 text-sm">{(["source", "node", "metric", "severity", "message"] as const).map((k) => <div key={k}><Label className="capitalize">{k}</Label><Input className="w-36" value={(t as any)[k]} onChange={(e) => setT({ ...t, [k]: e.target.value })} /></div>)}
      <Button variant="outline" onClick={() => api.post("/alerts/rules/test", t).then((r) => setRes(r.data)).catch(err)}>Test (nothing is created)</Button>
      {res && <span>Result: <Badge>{res.result}</Badge> {res.rule ? `by “${res.rule}”` : "no rule matched"}{res.event && res.event.severity !== t.severity ? `, severity → ${res.event.severity}` : ""}</span>}</CardContent></Card></div>;
}

function DirectoryTab() {
  const [csv, setCsv] = useState("email,name,active,group\nnew.joiner@neurealm.com,New Joiner,true,Service Desk"); const [res, setRes] = useState<any>(null); const [miss, setMiss] = useState(false); const [last, setLast] = useState<any>({});
  useEffect(() => { api.get("/directory/last").then((r) => setLast(r.data)); }, []);
  const parse = () => { const [h, ...ls] = csv.trim().split(/\r?\n/); const ks = h.split(",").map((x) => x.trim()); return ls.filter(Boolean).map((l) => { const v = l.split(","); const o: any = {}; ks.forEach((k, i) => (o[k] = (v[i] || "").trim())); o.active = o.active ? o.active !== "false" : true; return o; }); };
  const run = (dry: boolean) => api.post("/directory/sync", { users: parse(), dry_run: dry, deactivate_missing: miss }).then((r) => { setRes(r.data); if (!dry) { toast.success("Directory synced"); api.get("/directory/last").then((x) => setLast(x.data)); } }).catch(err);
  return <div className="grid gap-4 lg:grid-cols-2"><Card><CardHeader><CardTitle>Directory sync</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
    <p className="text-muted-foreground">Paste an export from your directory (Entra ID, Google Workspace or LDAP) or call <code>POST /api/directory/sync</code> on a schedule. Columns: email, name, active, group, role (end_user or agent).</p>
    <Textarea rows={8} className="font-mono text-xs" aria-label="Directory CSV" value={csv} onChange={(e) => setCsv(e.target.value)} />
    <label className="flex items-center gap-2"><Switch checked={miss} onCheckedChange={setMiss} />Deactivate people missing from this list</label>
    <div className="flex gap-2"><Button variant="outline" onClick={() => run(true)}>Preview</Button><Button disabled={!res?.dry_run} onClick={() => run(false)}>Apply</Button></div>
    {last.at && <p className="text-xs text-muted-foreground">Last sync {last.at}: {last.create} created, {last.update} updated, {last.deactivate} deactivated.</p>}</CardContent></Card>
    <Card><CardHeader><CardTitle>{res ? (res.dry_run ? "Preview" : "Applied") : "Result"}</CardTitle></CardHeader><CardContent className="space-y-2 text-sm">{res ? (["create", "update", "deactivate"] as const).map((k) => <div key={k}><b className="capitalize">{k}</b> ({res[k].length}): <span className="text-muted-foreground">{res[k].join(", ") || "none"}</span></div>).concat(res.errors.map((e: any, i: number) => <div key={"e" + i} className="text-red-600">Row {e.row + 1}: {e.error}</div>)) : <p className="text-muted-foreground">Preview first. Nothing changes until you press Apply. Admin accounts are never changed by sync.</p>}</CardContent></Card></div>;
}

function BackupTab() {
  const [hr, setHr] = useState<any>(null);
  useEffect(() => { api.get("/hr/settings").then((r) => setHr(r.data)); }, []);
  return <div className="grid gap-4 lg:grid-cols-2"><Card><CardHeader><CardTitle>Backup & export</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
    <p className="text-muted-foreground">Download everything in your workspace: tickets of every module, users (no passwords) and knowledge articles. Secrets in ticket data are masked. Each download is written to the audit log.</p>
    <div className="flex flex-wrap gap-2"><Button onClick={() => download("/admin/export")}><Download />Full backup (JSON)</Button><Button variant="outline" onClick={() => download("/admin/export?fmt=zip")}><Download />Spreadsheets (CSV zip)</Button></div>
    <p className="text-xs text-muted-foreground">The database itself is also backed up by your Postgres provider.</p></CardContent></Card>
    {hr && <Card><CardHeader><CardTitle>Onboarding & offboarding</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
      <label className="flex items-center gap-2"><Switch checked={hr.deactivate_on_offboard} onCheckedChange={(v: boolean) => api.put("/hr/settings", { deactivate_on_offboard: v }).then((r) => { setHr(r.data); toast.success("Saved"); }).catch(err)} />Deactivate the person's Neurealm Service Desk account when their offboarding is complete</label>
      <p className="text-muted-foreground">Start onboarding or offboarding from <Link className="text-primary underline" to="/hr">Onboarding / Offboarding</Link>. Each one creates a case with tasks for IT, facilities and HR.</p></CardContent></Card>}</div>;
}

function ErrorsTab() {
  const [e, setE] = useState<any[]>([]); const [open, setOpen] = useState<number | null>(null);
  const load = () => api.get("/admin/errors").then((r) => setE(r.data)); useEffect(() => { load(); }, []);
  return <Card><CardHeader className="flex-row items-center justify-between"><CardTitle>Error log</CardTitle><div className="flex gap-2"><Button size="sm" variant="outline" onClick={load}>Refresh</Button><Button size="sm" variant="ghost" onClick={() => api.delete("/admin/errors").then(load)}>Clear</Button></div></CardHeader>
    <CardContent className="text-sm">{e.length ? e.map((x) => <div key={x.id} className="border-b py-2 last:border-0"><button className="flex w-full items-center gap-2 text-start" onClick={() => setOpen(open === x.id ? null : x.id)}><Badge tone={x.kind === "server" ? "red" : "amber"}>{x.kind}</Badge><span className="flex-1 truncate">{x.message}</span><span className="text-xs text-muted-foreground">{x.path} · {x.at.replace("T", " ")}</span></button>
      {open === x.id && x.detail && <pre className="mt-2 max-h-60 overflow-auto rounded bg-muted p-2 text-xs">{x.detail}</pre>}</div>)
      : <EmptyState icon={AlertTriangle} title="No errors logged" desc="Server errors and browser errors show up here. The list keeps the latest 300 and resets when the server restarts." />}</CardContent></Card>;
}

export default function Platform() {
  const [tab, setTab] = useState("email");
  return <Page title="Platform & data" icon={Server} subtitle="Connect email, alerts and your directory, and look after your data. Chat tools and webhooks live under Integrations." wide>
    <Tabs value={tab} onValueChange={setTab}><TabsList><TabsTrigger value="email"><Mail />Email</TabsTrigger><TabsTrigger value="alerts"><Bell />Alert rules</TabsTrigger><TabsTrigger value="dir"><Users />Directory</TabsTrigger><TabsTrigger value="backup"><DatabaseBackup />Backup & HR</TabsTrigger><TabsTrigger value="errors"><AlertTriangle />Error log</TabsTrigger></TabsList>
      <TabsContent value="email"><EmailTab /></TabsContent><TabsContent value="alerts"><AlertsTab /></TabsContent><TabsContent value="dir"><DirectoryTab /></TabsContent><TabsContent value="backup"><BackupTab /></TabsContent><TabsContent value="errors"><ErrorsTab /></TabsContent></Tabs>
  </Page>;
}

const EP = [["GET", "/api/v1/modules", "List modules you can use"], ["GET", "/api/v1/records/{module}?state=&limit=50&offset=0", "List records, newest first"], ["GET", "/api/v1/records/{module}/{number}", "Get one record by number"],
  ["POST", "/api/v1/records/{module}", "Create a record: {title, description, data}"], ["POST", "/api/v1/records/{module}/{number}/comments", "Add a comment: {body, internal}"],
  ["POST", "/api/alerts/ingest", "Send monitoring alerts: [{source, node, metric, severity, message}]"], ["POST", "/api/directory/sync", "Sync users (admin key): {users, dry_run}"], ["GET", "/api/admin/export", "Download a backup (admin key)"]];
export function Developers() {
  const base = import.meta.env.VITE_API_URL || location.origin;
  return <Page title="Developer API" icon={Code2} subtitle="Use Neurealm Service Desk from scripts and other tools with a personal API key.">
    <Card><CardHeader><CardTitle>Get started</CardTitle></CardHeader><CardContent className="space-y-2 text-sm"><p>1. Create a key on <Link className="text-primary underline" to="/account">your account page</Link>. Keys act as you and follow your permissions. Revoke them there anytime.</p>
      <p>2. Send it as a bearer token:</p><pre tabIndex={0} className="overflow-x-auto rounded-lg bg-muted p-3 text-xs">{`curl -H "Authorization: Bearer nrsd_your_key" ${base}/api/v1/records/incident?limit=5

curl -X POST -H "Authorization: Bearer nrsd_your_key" -H "Content-Type: application/json" \\
  -d '{"title":"Disk almost full on web-01"}' ${base}/api/v1/records/incident`}</pre>
      <p>Full interactive reference: <a className="text-primary underline" href={`${base}/docs`} target="_blank" rel="noreferrer">{base}/docs</a></p></CardContent></Card>
    <Card><CardHeader><CardTitle>Endpoints</CardTitle></CardHeader><CardContent><table className="w-full text-sm"><tbody>{EP.map(([m, p, d]) => <tr key={p}><td className="td w-16"><Badge tone={m === "GET" ? "blue" : "green"}>{m}</Badge></td><td className="td font-mono text-xs">{p}</td><td className="td text-muted-foreground">{d}</td></tr>)}</tbody></table></CardContent></Card>
  </Page>;
}
