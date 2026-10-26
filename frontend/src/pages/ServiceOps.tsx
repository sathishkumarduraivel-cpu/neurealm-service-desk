import { useEffect, useState } from "react";
import { toast } from "sonner";
import { CalendarClock, Plus, Trash2 } from "lucide-react";
import { api, errMsg } from "../api";
import { Page, fmt } from "../ui";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, NativeSelect } from "@/components/ui/input";
import { Switch } from "@/components/ui/misc";
import { cn, humanize } from "@/lib/utils";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export default function ServiceOps() {
  const [c, setC] = useState<any>(null); const [groups, setGroups] = useState<any[]>([]); const [users, setUsers] = useState<any[]>([]); const [now, setNow] = useState<any>({});
  const [hol, setHol] = useState(""); const [sh, setSh] = useState({ group: "", user_id: 0, start: "", end: "" }); const [preview, setPreview] = useState<any>(null);
  const load = () => { api.get("/service-ops/config").then((r) => setC(r.data)); api.get("/service-ops/oncall/now").then((r) => setNow(r.data)); };
  useEffect(() => { load(); api.get("/groups").then((r) => setGroups(r.data)); api.get("/users").then((r) => setUsers(r.data.filter((u: any) => u.role !== "end_user"))); }, []);
  const put = async (path: string, body: any, msg = "Saved") => { try { await api.put(`/service-ops/${path}`, body); toast.success(msg); load(); } catch (x) { toast.error("Couldn't save", { description: errMsg(x) }); } };
  if (!c) return null; const cal = c.calendar; const esc = c.escalation; const setCal = (k: string, v: any) => setC({ ...c, calendar: { ...cal, [k]: v } });
  return (
    <Page title="SLA & assignment" icon={CalendarClock} subtitle="Working hours, holidays, escalation, who picks up new tickets, and who's on call.">
      <div className="grid gap-5 lg:grid-cols-2">
        <Card><CardHeader><div><CardTitle>Business hours</CardTitle><CardDescription>When on, SLA clocks only tick during working hours and skip holidays.</CardDescription></div></CardHeader><CardContent className="space-y-3 text-sm">
          <label className="flex items-center justify-between"><span>Use business hours for SLAs</span><Switch checked={cal.enabled} onCheckedChange={(v) => setCal("enabled", v)} /></label>
          <div className="flex flex-wrap gap-1.5">{DAYS.map((d, i) => <button key={d} type="button" onClick={() => setCal("days", cal.days.includes(i) ? cal.days.filter((x: number) => x !== i) : [...cal.days, i].sort())}
            className={cn("rounded-full border px-3 py-1 text-xs", cal.days.includes(i) ? "border-primary bg-primary/10 text-primary" : "text-muted-foreground")}>{d}</button>)}</div>
          <div className="grid grid-cols-3 gap-2"><div><Label>Starts</Label><Input aria-label="Starts" type="time" value={cal.start} onChange={(e) => setCal("start", e.target.value)} /></div><div><Label>Ends</Label><Input aria-label="Ends" type="time" value={cal.end} onChange={(e) => setCal("end", e.target.value)} /></div>
            <div><Label>UTC offset (min)</Label><Input aria-label="UTC offset (min)" type="number" value={cal.tz_offset_min} onChange={(e) => setCal("tz_offset_min", +e.target.value)} /></div></div>
          <div><Label>Holidays</Label><div className="mb-2 flex flex-wrap gap-1.5">{cal.holidays.map((h: string) => <Badge key={h} tone="neutral">{h}<button className="ms-1" aria-label={`Remove ${h}`} onClick={() => setCal("holidays", cal.holidays.filter((x: string) => x !== h))}>×</button></Badge>)}{!cal.holidays.length && <span className="text-xs text-muted-foreground">None yet</span>}</div>
            <div className="flex gap-2"><Input type="date" value={hol} onChange={(e) => setHol(e.target.value)} /><Button size="sm" variant="outline" disabled={!hol} onClick={() => { setCal("holidays", [...new Set([...cal.holidays, hol])]); setHol(""); }}><Plus />Add</Button></div></div>
          <div className="flex items-center gap-2"><Button size="sm" onClick={() => put("calendar", cal)}>Save hours</Button>
            <Button size="sm" variant="ghost" onClick={async () => setPreview((await api.post("/service-ops/preview-due?minutes=480")).data)}>Preview an 8-hour SLA</Button></div>
          {preview && <p className="text-xs text-muted-foreground">Starting now, an 8-hour SLA is due <b>{fmt(preview.business)}</b> (plain clock: {fmt(preview.wall_clock)}).</p>}
        </CardContent></Card>
        <Card><CardHeader><div><CardTitle>Escalation</CardTitle><CardDescription>What happens as a ticket gets close to, or past, its SLA.</CardDescription></div></CardHeader><CardContent className="space-y-3 text-sm">
          <div><Label>Warn when this much of the SLA is used (%)</Label><Input aria-label="Warn when this much of the SLA is used (%)" type="number" value={esc.warn_pct} onChange={(e) => setC({ ...c, escalation: { ...esc, warn_pct: +e.target.value } })} /></div>
          <label className="flex items-center justify-between"><span>Raise priority on breach</span><Switch checked={esc.bump_priority} onCheckedChange={(v) => setC({ ...c, escalation: { ...esc, bump_priority: v } })} /></label>
          <label className="flex items-center justify-between"><span>Tell admins on breach</span><Switch checked={esc.notify_admins} onCheckedChange={(v) => setC({ ...c, escalation: { ...esc, notify_admins: v } })} /></label>
          <Button size="sm" onClick={() => put("escalation", esc)}>Save escalation</Button>
          <p className="text-xs text-muted-foreground">Need more? Build a workflow with the “SLA at risk” or “SLA breached” trigger.</p></CardContent></Card>
        <Card><CardHeader><div><CardTitle>Assignment policies</CardTitle><CardDescription>How a person is picked when a ticket lands in a group.</CardDescription></div></CardHeader><CardContent className="space-y-2 text-sm">
          {groups.map((g) => <div key={g.id} className="flex items-center justify-between gap-3"><span className="truncate">{g.name}</span>
            <NativeSelect className="w-44" value={c.policies[g.name] || "manual"} onChange={(e) => setC({ ...c, policies: { ...c.policies, [g.name]: e.target.value } })}>{c.policy_types.map((p: string) => <option key={p} value={p}>{humanize(p)}</option>)}</NativeSelect></div>)}
          <Button size="sm" onClick={() => put("policies", { policies: c.policies })}>Save policies</Button></CardContent></Card>
        <Card><CardHeader><div><CardTitle>On-call rota</CardTitle><CardDescription>Used by the “On call” policy and shown to the desk.</CardDescription></div></CardHeader><CardContent className="space-y-3 text-sm">
          <div className="divide-y rounded-lg border">{c.oncall.length === 0 && <p className="p-3 text-muted-foreground">No shifts yet.</p>}{c.oncall.map((s: any) => <div key={s.id} className="flex items-center gap-3 p-3">
            <div className="flex-1"><b className="font-medium">{s.name}</b> <span className="text-muted-foreground">· {s.group}</span><div className="text-xs text-muted-foreground">{s.start.replace("T", " ")} → {s.end.replace("T", " ")}</div></div>
            {now[s.group]?.id === s.id && <Badge tone="green">On call now</Badge>}
            <button aria-label="Remove shift" onClick={async () => { await api.delete(`/service-ops/oncall/${s.id}`); load(); }}><Trash2 className="size-4 text-muted-foreground" /></button></div>)}</div>
          <div className="grid grid-cols-2 gap-2"><NativeSelect value={sh.group} onChange={(e) => setSh({ ...sh, group: e.target.value })}><option value="">Group…</option>{groups.map((g) => <option key={g.id}>{g.name}</option>)}</NativeSelect>
            <NativeSelect value={sh.user_id || ""} onChange={(e) => setSh({ ...sh, user_id: +e.target.value })}><option value="">Person…</option>{users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</NativeSelect>
            <Input type="datetime-local" value={sh.start} onChange={(e) => setSh({ ...sh, start: e.target.value })} /><Input type="datetime-local" value={sh.end} onChange={(e) => setSh({ ...sh, end: e.target.value })} /></div>
          <Button size="sm" disabled={!sh.group || !sh.user_id || !sh.start || !sh.end} onClick={async () => { try { await api.post("/service-ops/oncall", sh); toast.success("Shift added"); load(); } catch (x) { toast.error(errMsg(x)); } }}><Plus />Add shift</Button>
        </CardContent></Card>
      </div>
    </Page>
  );
}
