import type { ComponentType, ReactNode } from "react";
import { AppWindow, ArrowDownRight, ArrowDownLeft, ArrowUpRight, BookOpen, Bot, Check, CheckCircle2, Cloud, Database, Flag, FlaskConical, HardDrive, Laptop, Lock, Network, Octagon, Package, PartyPopper, Plus, Rocket, Server, ShieldCheck, Sparkles, TriangleAlert, UserCog, Zap, CircleDot } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { titleFor } from "./nav";
import { Skeleton } from "@/components/ui/misc";
import { Badge, Dot, type Tone } from "@/components/ui/badge";
import { cn, humanize } from "@/lib/utils";
import { useT } from "@/i18n";

const PT: Record<string, [Tone, string]> = { P1: ["red", "Critical"], P2: ["orange", "High"], P3: ["amber", "Moderate"], P4: ["neutral", "Low"], P5: ["neutral", "Planning"] };
export const Priority = ({ p, label }: { p: string; label?: boolean }) => {
  const { t: tr } = useT(); const [t, l] = PT[p] || ["neutral", p]; return <Badge tone={t} className="font-semibold tabular-nums"><PriorityBars p={p} />{p}{label && <span className="font-normal">· {tr(l)}</span>}</Badge>;
};
const PriorityBars = ({ p }: { p: string }) => { const n = { P1: 3, P2: 3, P3: 2, P4: 1 }[p] ?? 1; return <span className="inline-flex items-end gap-px h-2.5">{[1, 2, 3].map((i) => <span key={i} className={cn("w-[2px] rounded-sm bg-current", i > n && "opacity-25")} style={{ height: 3 + i * 2.5 }} />)}</span>; };

export const stateTone = (s: string): Tone => {
  const v = s.toLowerCase();
  if (/(resolved|closed|done|complete|approved|fulfilled|met|active_ok|healthy|compliant|passed|success|delivered|installed|in_use|operational|published|green|mitigated|remediated|signed)/.test(v)) return "green";
  if (/(cancel|reject|fail|breach|retired|disposed|expired|critical|red|halted|blocked|error|lost)/.test(v)) return "red";
  if (/(pending|hold|await|wait|review|requested|scheduled|assess|planned|draft_review|at_risk|amber|triage|paused)/.test(v)) return "amber";
  if (/(progress|assigned|working|implement|active|dispatched|en_route|investigat|running|open_ok|rollout|executing)/.test(v)) return "brand";
  if (/(new|open|submitted|identified|logged|received|proposed)/.test(v)) return "blue";
  return "neutral";
};
export const State = ({ s }: { s: string }) => { const { t: tr } = useT(); const t = stateTone(s || ""); return <Badge tone={t} className="capitalize"><Dot tone={t} />{tr(humanize(s))}</Badge>; };
const ST: Record<string, Tone> = { breached: "solidRed", at_risk: "amber", on_track: "green", met: "green", none: "neutral" };
export const Sla = ({ s }: { s: string }) => { const { t } = useT(); return s === "none" || !s ? <span className="text-xs text-muted-foreground">—</span> : <Badge tone={ST[s] || "neutral"} className="capitalize">{t(humanize(s))}</Badge>; };

const ICONS = { bot: Bot, sparkles: Sparkles, flag: Flag, check: Check, checkCircle: CheckCircle2, plus: Plus, lock: Lock, flask: FlaskConical, rocket: Rocket, stop: Octagon, go: CircleDot, shield: ShieldCheck,
  zap: Zap, warn: TriangleAlert, party: PartyPopper, tech: UserCog, up: ArrowUpRight, down: ArrowDownLeft, server: Server, app: AppWindow, db: Database, net: Network, laptop: Laptop, cloud: Cloud, disk: HardDrive, pkg: Package };
export type IcoName = keyof typeof ICONS;
export const Ico = ({ n, className }: { n: IcoName; className?: string }) => { const I = ICONS[n]; return <I className={cn("inline size-4 shrink-0 align-[-3px]", className)} />; };
export const PageLoading = () => <div className="space-y-4"><div className="grid grid-cols-2 gap-4 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[92px]" />)}</div><Skeleton className="h-72" /></div>;

export function Page({ title, subtitle, icon, actions, children, className, wide }: { title: ReactNode; subtitle?: ReactNode; icon?: ComponentType<{ className?: string }>; actions?: ReactNode; children: ReactNode; className?: string; wide?: boolean }) {
  const loc = useLocation(); const I = icon || titleFor(loc.pathname)?.icon;
  return (
    <div className={cn("mx-auto w-full px-6 py-6 space-y-5", wide ? "max-w-none" : "max-w-[1440px]", className)}>
      {title !== "" && <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          {I && <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border bg-card shadow-xs"><I className="size-[18px] text-primary" /></div>}
          <div className="min-w-0"><h1 className="truncate text-xl font-semibold tracking-tight">{title}</h1>{subtitle && <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>}</div>
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>}
      {children}
    </div>
  );
}
export const fmt = (d?: string | null) => (d ? new Date(d + (/[zZ]|[+-]\d\d:?\d\d$/.test(d) ? "" : "Z")).toLocaleString(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—");

const TONE_MAP: Record<string, string> = { "text-red-600": "text-red-600", "text-emerald-600": "text-emerald-600", "text-amber-600": "text-amber-600", "text-brand-600": "text-primary" };
export function Stat({ label, value, tone = "", icon: I, delta, deltaGood = "up", hint }: { label: string; value: ReactNode; tone?: string; icon?: ComponentType<{ className?: string }>; delta?: number | null; deltaGood?: "up" | "down"; hint?: ReactNode }) {
  const good = delta == null ? null : (delta >= 0) === (deltaGood === "up");
  return (
    <div className="rounded-lg border bg-card p-4 shadow-xs">
      <div className="flex items-center justify-between text-xs font-medium text-muted-foreground"><span className="truncate">{label}</span>{I && <I className="size-4 text-muted-foreground/70" />}</div>
      <div className={cn("mt-2 text-2xl font-semibold tracking-tight tabular-nums", TONE_MAP[tone] || tone)}>{value}</div>
      {(delta != null || hint) && <div className="mt-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
        {delta != null && <span className={cn("inline-flex items-center gap-0.5 rounded px-1 py-px font-medium", good ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700")}>
          {delta >= 0 ? <ArrowUpRight className="size-3" /> : <ArrowDownRight className="size-3" />}{Math.abs(delta)}%</span>}{hint}</div>}
    </div>
  );
}

export function AiPanel({ s }: { s: any }) {
  if (!s || !s.category) return null;
  const pct = Math.round((s.confidence || 0) * 100);
  return (
    <div className="relative overflow-hidden rounded-lg border border-indigo-200/80 bg-gradient-to-b from-indigo-50/80 to-card shadow-xs">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-indigo-400 to-transparent" />
      <div className="flex items-center justify-between px-4 pt-3.5">
        <div className="flex items-center gap-2 text-sm font-semibold"><span className="flex size-6 items-center justify-center rounded-md bg-gradient-to-br from-indigo-500 to-violet-500 text-white shadow-sm"><Sparkles className="size-3.5" /></span>Neurealm AI</div>
        <span className="text-[11px] text-muted-foreground">{s.engine}</span>
      </div>
      <div className="px-4 pb-4 pt-3 space-y-3">
        <div>
          <div className="flex justify-between text-xs"><span className="text-muted-foreground">Confidence</span><span className="font-medium tabular-nums">{pct}%</span></div>
          <div className="mt-1 h-1.5 rounded-full bg-indigo-100"><div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500" style={{ width: `${pct}%` }} /></div>
        </div>
        <dl className="grid grid-cols-3 gap-2 text-sm">
          <div className="rounded-md border bg-card/70 px-2.5 py-2"><dt className="text-[11px] text-muted-foreground">Category</dt><dd className="mt-0.5 font-medium capitalize truncate">{s.category}</dd></div>
          <div className="rounded-md border bg-card/70 px-2.5 py-2"><dt className="text-[11px] text-muted-foreground">Priority</dt><dd className="mt-0.5"><Priority p={s.priority} /></dd></div>
          <div className="rounded-md border bg-card/70 px-2.5 py-2"><dt className="text-[11px] text-muted-foreground">Route to</dt><dd className="mt-0.5 font-medium truncate" title={s.assignment_group}>{s.assignment_group}</dd></div>
        </dl>
        {s.reasoning && <p className="text-xs leading-relaxed text-muted-foreground">{s.reasoning}</p>}
        {s.kb_suggestions?.length > 0 && <div><div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Suggested knowledge</div>
          <div className="space-y-1">{s.kb_suggestions.map((k: any) => <Link key={k.id} to={`/knowledge/${k.id}`} className="flex items-center gap-2 rounded-md border bg-card px-2.5 py-1.5 text-xs hover:border-indigo-300 hover:bg-indigo-50/50">
            <BookOpen className="size-3.5 text-indigo-500" /><span className="font-mono text-muted-foreground">{k.number}</span><span className="truncate">{k.title}</span></Link>)}</div></div>}
      </div>
    </div>
  );
}
export const SectionTitle = ({ children, action }: { children: ReactNode; action?: ReactNode }) => <div className="flex items-center justify-between"><h3 className="text-sm font-semibold">{children}</h3>{action}</div>;
