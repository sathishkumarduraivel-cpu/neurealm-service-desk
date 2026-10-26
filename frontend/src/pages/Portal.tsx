import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, BookOpen, ChevronRight, LifeBuoy, Search, ShoppingBag, Sparkles, Ticket } from "lucide-react";
import { api, type Rec } from "../api";
import { useAuth } from "../auth";
import { State } from "../ui";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/misc";
import { CatalogIcon } from "./Catalog";
import { relTime } from "@/lib/utils";

const POPULAR = ["VPN not connecting", "Reset my password", "Outlook not syncing", "Request a new laptop"];
export default function Portal() {
  const { user } = useAuth(); const nav = useNavigate(); const [q, setQ] = useState(""); const [kb, setKb] = useState<any[]>([]);
  const [mine, setMine] = useState<Rec[] | null>(null); const [reqs, setReqs] = useState<Rec[] | null>(null); const [cat, setCat] = useState<any[]>([]); const [arts, setArts] = useState<any[]>([]);
  useEffect(() => {
    api.get("/records/incident", { params: { limit: 50 } }).then((r) => setMine(r.data.filter((x: Rec) => x.requester?.id === user?.id).slice(0, 5)));
    api.get("/records/request", { params: { limit: 50 } }).then((r) => setReqs(r.data.filter((x: Rec) => x.requester?.id === user?.id).slice(0, 5)));
    api.get("/catalog").then((r) => setCat(r.data.slice(0, 8))); api.get("/kb").then((r) => setArts(r.data.slice(0, 5))).catch(() => {});
  }, []);
  useEffect(() => { if (q.length < 3) { setKb([]); return; } const t = setTimeout(() => api.get("/ai/kb-suggest", { params: { q } }).then((r) => setKb(r.data)), 300); return () => clearTimeout(t); }, [q]);
  const Row = ({ r, to, label }: { r: Rec; to: string; label: string }) => <Link to={to} className="-mx-2 flex items-center gap-3 rounded-md px-2 py-2 text-sm hover:bg-muted/50"><span className="w-24 shrink-0 font-mono text-xs text-muted-foreground">{r.number}</span><span className="flex-1 truncate">{label}</span><span className="hidden text-xs text-muted-foreground sm:inline">{relTime(r.created_at)}</span><State s={r.state} /></Link>;
  return (
    <div>
      <section className="relative overflow-hidden border-b bg-[#0b0d1f] text-white">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_80%_at_15%_0%,rgba(99,102,241,0.5),transparent_60%),radial-gradient(ellipse_50%_70%_at_95%_100%,rgba(139,92,246,0.35),transparent_60%)]" />
        <div className="absolute inset-0 opacity-[0.06] [background-image:linear-gradient(to_right,white_1px,transparent_1px),linear-gradient(to_bottom,white_1px,transparent_1px)] [background-size:36px_36px]" />
        <div className="relative mx-auto max-w-3xl px-6 py-16 text-center">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-white/80"><Sparkles className="size-3.5 text-indigo-200" />Answers powered by Neurealm AI</div>
          <h1 className="mt-5 text-4xl font-semibold tracking-tight">Hi {user?.full_name.split(" ")[0]}, how can we help?</h1>
          <p className="mt-3 text-white/65">Search knowledge, request services or report an issue. We'll route it to the right team automatically.</p>
          <div className="relative mx-auto mt-8 max-w-2xl text-start">
            <div className="flex items-center gap-2 rounded-xl bg-white p-1.5 ps-4 shadow-2xl shadow-indigo-950/40 ring-1 ring-white/20"><Search className="size-5 text-slate-400" />
              <input className="h-11 flex-1 bg-transparent text-base text-slate-900 outline-none placeholder:text-slate-400" placeholder="Describe your issue, e.g. “My VPN keeps disconnecting”" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && nav("/incidents/new")} />
              <Button size="lg" className="rounded-lg" onClick={() => nav("/incidents/new")}>Get help<ArrowRight /></Button></div>
            {kb.length > 0 && <div className="absolute inset-x-0 top-full z-10 mt-2 overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-pop"><div className="flex items-center gap-1.5 border-b px-4 py-2 text-xs font-medium text-muted-foreground"><Sparkles className="size-3.5 text-indigo-500" />Suggested answers</div>
              {kb.map((k) => <Link key={k.id} to={`/knowledge/${k.id}`} className="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-accent"><BookOpen className="size-4 text-muted-foreground" /><span className="flex-1">{k.title}</span><ChevronRight className="size-4 text-muted-foreground" /></Link>)}</div>}
          </div>
          <div className="mt-5 flex flex-wrap justify-center gap-2 text-xs">{POPULAR.map((p) => <button key={p} onClick={() => setQ(p)} className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-white/75 transition-colors hover:bg-white/10 hover:text-white">{p}</button>)}</div>
        </div>
      </section>
      <div className="mx-auto max-w-[1200px] space-y-8 px-6 py-8">
        <div className="grid gap-4 md:grid-cols-3">
          {[[LifeBuoy, "Report an issue", "Something broken? Tell us and we'll fix it.", "/incidents/new"], [ShoppingBag, "Request something", "Hardware, software, access and more.", "/catalog"], [BookOpen, "Browse knowledge", "Step-by-step guides and FAQs.", "/knowledge"]].map(([I, t, d, to]: any) =>
            <Link key={t} to={to} className="group flex items-start gap-4 rounded-xl border bg-card p-5 shadow-xs transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-soft">
              <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary"><I className="size-5" /></div>
              <div className="flex-1"><div className="font-medium">{t}</div><div className="mt-0.5 text-sm text-muted-foreground">{d}</div></div><ArrowRight className="mt-1 size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" /></Link>)}
        </div>
        <div>
          <div className="mb-3 flex items-end justify-between"><div><h2 className="text-base font-semibold">Popular services</h2><p className="text-sm text-muted-foreground">Most requested by your colleagues</p></div><Link to="/catalog" className="text-sm font-medium text-primary hover:underline">View catalog</Link></div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{cat.length === 0 ? [...Array(4)].map((_, i) => <Skeleton key={i} className="h-[92px]" />) : cat.map((c) =>
            <Link key={c.id} to="/catalog" className="group flex items-center gap-3 rounded-xl border bg-card p-4 shadow-xs transition-all hover:border-primary/30 hover:shadow-soft"><CatalogIcon c={c} />
              <div className="min-w-0"><div className="truncate text-sm font-medium">{c.name}</div><div className="truncate text-xs text-muted-foreground">{c.category}</div></div></Link>)}</div>
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <Card><CardHeader><CardTitle className="flex items-center gap-2"><Ticket className="size-4 text-muted-foreground" />My open tickets</CardTitle><Link to="/incidents" className="text-xs font-medium text-primary hover:underline">All</Link></CardHeader><CardContent>
            {mine === null ? <Skeleton className="h-24" /> : mine.length ? mine.map((r) => <Row key={r.id} r={r} to={`/incidents/${r.id}`} label={r.title} />) : <EmptyState title="No open tickets" desc="You're all set. Anything you report will show up here." />}</CardContent></Card>
          <Card><CardHeader><CardTitle className="flex items-center gap-2"><ShoppingBag className="size-4 text-muted-foreground" />My requests</CardTitle><Link to="/requests" className="text-xs font-medium text-primary hover:underline">All</Link></CardHeader><CardContent>
            {reqs === null ? <Skeleton className="h-24" /> : reqs.length ? reqs.map((r) => <Row key={r.id} r={r} to={`/requests/${r.id}`} label={r.data.item || r.title} />) : <EmptyState title="No requests yet" desc="Order hardware, software or access from the catalog." />}</CardContent></Card>
          <Card><CardHeader><CardTitle className="flex items-center gap-2"><BookOpen className="size-4 text-muted-foreground" />Top articles</CardTitle><Link to="/knowledge" className="text-xs font-medium text-primary hover:underline">All</Link></CardHeader><CardContent>
            {arts.map((a) => <Link key={a.id} to={`/knowledge/${a.id}`} className="-mx-2 flex items-center gap-2 rounded-md px-2 py-2 text-sm hover:bg-muted/50"><span className="flex-1 truncate">{a.title}</span><span className="text-xs text-muted-foreground tabular-nums">{a.views} views</span></Link>)}</CardContent></Card>
        </div>
      </div>
    </div>
  );
}
