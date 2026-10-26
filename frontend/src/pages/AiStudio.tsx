import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarChart3, Download, Sparkles } from "lucide-react";
import { api, errMsg } from "../api";
import { Page } from "../ui";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { Switch } from "@/components/ui/misc";

const EX = ["Open incidents by priority last 30 days", "Requests by state last 90 days", "Incidents by team last 60 days", "Changes by month last 12 months", "P1 incidents by assignee last 30 days"];
export function AiReports() {
  const [q, setQ] = useState(EX[0]); const [r, setR] = useState<any>(null); const [busy, setBusy] = useState(false);
  const run = (qq = q) => { setBusy(true); api.post("/ai/report", { question: qq }).then((x) => setR(x.data)).catch((x) => toast.error(errMsg(x))).finally(() => setBusy(false)); };
  useEffect(() => { run(); }, []);
  const csv = () => { const b = new Blob(["label,count\n" + r.rows.map((x: any) => `"${x.label}",${x.count}`).join("\n")], { type: "text/csv" }); const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "servicedesk-report.csv"; a.click(); };
  return (
    <Page title="Ask for a report" icon={BarChart3} subtitle="Type a question in plain words. Neurealm AI builds the chart (rules work even with AI turned off).">
      <Card><CardContent className="space-y-3 pt-5"><div className="flex gap-2"><Input aria-label="Report question" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && run()} /><Button onClick={() => run()} disabled={busy}><Sparkles />{busy ? "Building…" : "Build"}</Button></div>
        <div className="flex flex-wrap gap-1.5">{EX.map((e) => <button key={e} onClick={() => { setQ(e); run(e); }} className="rounded-full border px-2.5 py-0.5 text-xs text-muted-foreground hover:border-primary hover:text-foreground">{e}</button>)}</div></CardContent></Card>
      {r && <Card><CardHeader className="flex-row items-center justify-between"><CardTitle>{r.title} <Badge className="ms-2">{r.total} records</Badge><Badge className="ms-1">{r.engine === "llm" ? "AI" : "rules"}</Badge></CardTitle><Button size="sm" variant="outline" onClick={csv}><Download />CSV</Button></CardHeader>
        <CardContent><div className="h-72"><ResponsiveContainer>{r.chart === "line" ? <LineChart data={r.rows}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="label" fontSize={11} /><YAxis allowDecimals={false} fontSize={11} /><Tooltip /><Line dataKey="count" stroke="#1863DC" strokeWidth={2} /></LineChart>
          : <BarChart data={r.rows}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="label" fontSize={11} /><YAxis allowDecimals={false} fontSize={11} /><Tooltip /><Bar dataKey="count" fill="#1863DC" radius={[4, 4, 0, 0]} /></BarChart>}</ResponsiveContainer></div>
          <p className="mt-2 text-xs text-muted-foreground">Understood as: {r.spec.module}, grouped by {r.spec.group_by.replace("_", " ")}, last {r.spec.days} days{Object.keys(r.spec.filter).length ? `, filters: ${JSON.stringify(r.spec.filter)}` : ""}.</p></CardContent></Card>}
    </Page>
  );
}

const FEAT: Record<string, string> = { assistant: "Assistant chat", ticket: "Ticket summaries & replies", writing: "Writing help", reports: "Report builder", triage: "Ticket triage" };
export function AiSettings() {
  const [p, setP] = useState<any>(null); const [key, setKey] = useState("");
  useEffect(() => { api.get("/ai/provider").then((r) => setP(r.data)); }, []);
  const save = (extra: any = {}) => api.put("/ai/provider", { ...p, api_key: key || null, ...extra }).then((r) => { setP(r.data); setKey(""); toast.success("Neurealm AI settings saved"); }).catch((x) => toast.error(errMsg(x)));
  const test = () => api.post("/ai/provider/test").then((r) => (r.data.ok ? toast.success : toast)(r.data.message));
  if (!p) return null;
  return (
    <Page title="Neurealm AI" icon={Sparkles} subtitle="Connect any OpenAI-compatible provider. It's off by default, and Neurealm Service Desk keeps working with rules either way.">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card><CardHeader><CardTitle>Provider</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
          <label className="flex items-center gap-2"><Switch checked={p.enabled} onCheckedChange={(v: boolean) => setP({ ...p, enabled: v })} />Use an AI provider</label>
          <div><Label>API address</Label><Input aria-label="API address" value={p.base_url} onChange={(e) => setP({ ...p, base_url: e.target.value })} placeholder="https://api.openai.com/v1" /></div>
          <div><Label>Model</Label><Input aria-label="Model" value={p.model} onChange={(e) => setP({ ...p, model: e.target.value })} /></div>
          <div><Label>API key</Label><Input aria-label="API key" type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} placeholder={p.has_key ? `A key is set (${p.key_source}). Type to replace it.` : "Paste a key"} /></div>
          <div className="flex flex-wrap gap-2"><Button onClick={() => save()}>Save</Button><Button variant="outline" onClick={test}>Test connection</Button>{p.key_source === "saved" && <Button variant="ghost" onClick={() => save({ clear_key: true })}>Remove saved key</Button>}</div>
          <p className="text-xs text-muted-foreground">Keys are never shown again after saving. If the provider is slow or down, Neurealm Service Desk quietly switches back to rules.</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Where to use AI</CardTitle></CardHeader><CardContent className="space-y-2 text-sm">{Object.entries(FEAT).map(([k, l]) =>
          <label key={k} className="flex items-center gap-2"><Switch checked={p.features[k]} onCheckedChange={(v: boolean) => setP({ ...p, features: { ...p.features, [k]: v } })} />{l}</label>)}
          <p className="pt-2 text-xs text-muted-foreground">Switched-off features use the built-in rules.</p></CardContent></Card>
      </div>
    </Page>
  );
}
