import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, BookOpen, Eye, Search, Sparkles, Tag, ThumbsDown, ThumbsUp } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg } from "../api";
import { isStaff, useAuth } from "../auth";
import { Input, Textarea } from "@/components/ui/input";
import { Page } from "../ui";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, Skeleton } from "@/components/ui/misc";
import { cn, humanize } from "@/lib/utils";
export function Knowledge() {
  const [q, setQ] = useState(""); const [rows, setRows] = useState<any[] | null>(null); const [cat, setCat] = useState("");
  const load = (qq = q) => api.get("/kb", { params: { q: qq || undefined } }).then((r) => setRows(r.data));
  useEffect(() => { const t = setTimeout(() => load(), 250); return () => clearTimeout(t); }, [q]);
  const cats = [...new Set((rows || []).map((a) => a.category))]; const shown = (rows || []).filter((a) => !cat || a.category === cat);
  return (
    <Page title="Knowledge Base" icon={BookOpen} subtitle="Guides, fixes and FAQs curated by the service desk and Neurealm AI.">
      <div className="relative max-w-2xl"><Search className="pointer-events-none absolute start-3.5 top-1/2 size-[18px] -translate-y-1/2 text-muted-foreground" />
        <input className="input h-11 ps-10 text-base" placeholder="Search knowledge, e.g. vpn, password, outlook…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      {cats.length > 1 && <div className="flex flex-wrap gap-1.5">{["", ...cats].map((c) => <button key={c || "all"} onClick={() => setCat(c)} className={cn("rounded-full border px-3 py-1 text-xs font-medium capitalize transition-colors", cat === c ? "border-primary bg-primary text-primary-foreground" : "bg-card text-muted-foreground hover:text-foreground")}>{c || "All topics"}</button>)}</div>}
      {rows === null ? <div className="grid gap-4 md:grid-cols-2">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-28" />)}</div> : !shown.length ? <EmptyState icon={BookOpen} title="No articles found" desc="Try another keyword, or report an issue and an agent will help." /> :
        <div className="grid gap-4 md:grid-cols-2">{shown.map((a) => (
          <Link key={a.id} to={`/knowledge/${a.id}`} className="group rounded-xl border bg-card p-5 shadow-xs transition-all hover:border-primary/30 hover:shadow-soft">
            <div className="flex items-center gap-2 text-xs text-muted-foreground"><span className="font-mono">{a.number}</span><Badge className="capitalize">{a.category}</Badge>{a.ai_generated && <Badge tone="violet"><Sparkles className="size-3" />AI draft</Badge>}{!a.published && <Badge tone="amber">Unpublished</Badge>}
              <span className="ms-auto flex items-center gap-1"><Eye className="size-3.5" />{a.views}</span></div>
            <div className="mt-2.5 font-medium group-hover:text-primary">{a.title}</div><div className="mt-1 line-clamp-2 text-sm text-muted-foreground">{a.body}</div></Link>))}</div>}
    </Page>
  );
}
export function KnowledgeArticle() {
  const { id } = useParams(); const [a, setA] = useState<any>(null); const { user } = useAuth(); const staff = isStaff(user);
  const reload = () => api.get(`/kb/${id}`).then((r) => setA(r.data));
  useEffect(() => { reload(); }, [id]);
  const fb = (helpful: boolean) => api.post(`/kb/${id}/feedback`, { helpful }).then((r) => { setA({ ...a, ...r.data }); toast.success(helpful ? "Thanks, glad it helped!" : "Thanks, we'll improve this article."); }).catch((x) => toast(errMsg(x)));
  if (!a) return <Page title=""><Skeleton className="h-8 w-96" /><Skeleton className="h-96 max-w-3xl" /></Page>;
  return (
    <Page title="">
      <Link to="/knowledge" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" />Knowledge base</Link>
      <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
        <article className="max-w-3xl"><div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground"><span className="font-mono">{a.number}</span><Badge className="capitalize">{humanize(a.category)}</Badge>{a.ai_generated && <Badge tone="violet"><Sparkles className="size-3" />AI generated</Badge>}</div>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight">{a.title}</h1>
          <Card className="mt-6"><CardContent className="pt-5"><div className="whitespace-pre-wrap text-[15px] leading-7">{a.body}</div></CardContent></Card>
          <div className="mt-6 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">Was this helpful?<Button variant="outline" size="sm" onClick={() => fb(true)}><ThumbsUp />Yes</Button><Button variant="outline" size="sm" onClick={() => fb(false)}><ThumbsDown />No</Button><span className="text-xs">{a.helpful ?? 0} yes · {a.not_helpful ?? 0} no · version {a.version ?? 1}</span></div>
          {staff && <KbEditor a={a} onSaved={reload} />}</article>
        <aside className="space-y-4"><Card><CardContent className="space-y-3 pt-5 text-sm"><div className="flex justify-between"><span className="text-muted-foreground">Views</span><span className="font-medium tabular-nums">{a.views}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Status</span><Badge tone={a.published ? "green" : "amber"}>{a.published ? "Published" : "Draft"}</Badge></div>
          {a.tags && <div><div className="mb-2 flex items-center gap-1.5 text-muted-foreground"><Tag className="size-3.5" />Tags</div><div className="flex flex-wrap gap-1.5">{a.tags.split(",").map((t: string) => <Badge key={t}>{t.trim()}</Badge>)}</div></div>}</CardContent></Card>
          <Button variant="outline" className="w-full" asChild><Link to="/incidents/new">Still stuck? Report an issue</Link></Button></aside>
      </div>
    </Page>
  );
}

function KbEditor({ a, onSaved }: { a: any; onSaved: () => void }) {
  const [open, setOpen] = useState(false); const [t, setT] = useState(a.title); const [b, setB] = useState(a.body); const [vs, setVs] = useState<any[]>([]);
  useEffect(() => { if (open) api.get(`/kb/${a.id}/versions`).then((r) => setVs(r.data.versions)); }, [open, a.id, a.version]);
  const save = () => api.put(`/kb/${a.id}`, { title: t, body: b }).then(() => { toast.success("Saved as a new version"); onSaved(); }).catch((x) => toast.error(errMsg(x)));
  if (!open) return <Button variant="outline" size="sm" className="mt-4" onClick={() => setOpen(true)}>Edit article & history</Button>;
  return <Card className="mt-4"><CardContent className="space-y-3 pt-5"><Input value={t} onChange={(e) => setT(e.target.value)} /><Textarea rows={8} value={b} onChange={(e) => setB(e.target.value)} />
    <div className="flex gap-2"><Button size="sm" onClick={save}>Save new version</Button><Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Close</Button></div>
    <div className="border-t pt-3 text-sm"><div className="mb-2 font-medium">Version history</div>{!vs.length ? <p className="text-muted-foreground">No earlier versions yet.</p> :
      <ul className="space-y-1.5">{vs.map((v: any) => <li key={v.version} className="flex items-center justify-between gap-2"><span>v{v.version} · {v.title}</span><Button size="sm" variant="ghost" onClick={() => { setT(v.title); setB(v.body); }}>Load</Button></li>)}</ul>}</div>
  </CardContent></Card>;
}
