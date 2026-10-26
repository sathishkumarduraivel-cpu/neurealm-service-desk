import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { AlarmClock, Bell, CheckCheck, CheckCircle2, Flame, Info, Play, Siren, Sparkles } from "lucide-react";
import { api } from "../api";
import { Page, fmt } from "../ui";
import { Button } from "@/components/ui/button";
import { EmptyState, Skeleton } from "@/components/ui/misc";
import { cn, humanize, relTime } from "@/lib/utils";
const IC: Record<string, [any, string]> = { sla_warning: [AlarmClock, "bg-amber-100 text-amber-700"], sla_breach: [Flame, "bg-red-100 text-red-600"],
  escalation: [Siren, "bg-orange-100 text-orange-600"], approval: [CheckCircle2, "bg-emerald-100 text-emerald-600"],
  ai: [Sparkles, "bg-violet-100 text-violet-600"], info: [Info, "bg-sky-100 text-sky-600"] };
export default function Notifications() {
  const [rows, setRows] = useState<any[] | null>(null); const [tab, setTab] = useState<"all" | "unread">("all");
  const load = () => api.get("/notifications").then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);
  const shown = (rows || []).filter((n) => tab === "all" || !n.read); const unread = (rows || []).filter((n) => !n.read).length;
  return (
    <Page title="Inbox" icon={Bell} subtitle={`${unread} unread notification${unread === 1 ? "" : "s"}`} actions={<><Button variant="outline" onClick={async () => { await api.post("/sla/escalate").catch(() => {}); load(); toast.success("SLA job executed"); }}><Play />Run SLA job</Button>
      <Button onClick={async () => { await api.post("/notifications/read-all"); load(); toast.success("All caught up"); }}><CheckCheck />Mark all read</Button></>}>
      <div className="flex gap-1 rounded-lg border bg-card p-1 shadow-xs w-fit">{(["all", "unread"] as const).map((t) => <button key={t} onClick={() => setTab(t)} className={cn("rounded-md px-3 py-1 text-xs font-medium capitalize", tab === t ? "bg-secondary text-foreground shadow-xs" : "text-muted-foreground hover:text-foreground")}>{t}{t === "unread" && unread > 0 && <span className="ms-1.5 rounded bg-primary px-1 text-[10px] text-primary-foreground">{unread}</span>}</button>)}</div>
      <div className="overflow-hidden rounded-lg border bg-card shadow-xs">{rows === null ? <div className="space-y-3 p-4">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-12" />)}</div> : !shown.length ? <EmptyState icon={CheckCheck} title="You're all caught up" desc="New SLA warnings, escalations and approvals will appear here." /> :
        <ul className="divide-y">{shown.map((n) => { const [I, c] = IC[n.kind] || IC.info; return <li key={n.id} className={cn("flex items-start gap-3 px-4 py-3 transition-colors hover:bg-muted/40", n.read && "opacity-60")}>
          <span className={cn("mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg", c)}><I className="size-4" /></span>
          <div className="min-w-0 flex-1">{n.link ? <Link className="text-sm font-medium hover:text-primary" to={n.link} onClick={() => api.post(`/notifications/${n.id}/read`)}>{n.title}</Link> : <span className="text-sm font-medium">{n.title}</span>}
            <div className="mt-0.5 text-xs capitalize text-muted-foreground">{humanize(n.kind)} · <span title={fmt(n.created_at)}>{relTime(n.created_at)}</span></div></div>
          {!n.read && <span className="mt-2 size-2 shrink-0 rounded-full bg-primary" />}</li>; })}</ul>}</div>
    </Page>
  );
}
