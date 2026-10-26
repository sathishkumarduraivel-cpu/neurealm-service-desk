import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { BookOpen, Copy, Send, Sparkles, X } from "lucide-react";
import { api, errMsg } from "../api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export function AssistantWidget() {
  const [open, setOpen] = useState(false); const [q, setQ] = useState(""); const [busy, setBusy] = useState(false);
  const [msgs, setMsgs] = useState<any[]>([{ role: "assistant", content: "Hi! I'm Neurealm AI. Ask me about your tickets, or tell me what's not working." }]); const nav = useNavigate();
  const ask = async () => { const m = q.trim(); if (!m) return; setQ(""); const h = [...msgs, { role: "user", content: m }]; setMsgs(h); setBusy(true);
    try { const { data } = await api.post("/ai/assistant", { message: m, history: h.slice(-6) }); setMsgs([...h, { role: "assistant", content: data.answer, sources: data.sources, actions: data.actions, engine: data.engine }]); }
    catch (x) { setMsgs([...h, { role: "assistant", content: errMsg(x) }]); } finally { setBusy(false); } };
  const act = (a: any) => { setOpen(false); if (a.type === "catalog") nav("/catalog"); else if (a.type === "create_incident") nav(`/incidents/new?title=${encodeURIComponent(a.title)}`); };
  if (!open) return <button onClick={() => setOpen(true)} aria-label="Ask Neurealm AI" className="fixed bottom-5 end-5 z-40 flex items-center gap-2 rounded-full bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground shadow-lg hover:opacity-95"><Sparkles className="size-4" />Ask Neurealm AI</button>;
  return <div role="dialog" aria-label="Neurealm AI assistant" className="fixed bottom-5 end-5 z-40 flex h-[480px] w-[360px] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl border bg-card shadow-2xl">
    <div className="flex items-center gap-2 border-b bg-brand-50/60 px-4 py-3"><Sparkles className="size-4 text-primary" /><span className="font-semibold">Neurealm AI</span><button className="ms-auto" aria-label="Close" onClick={() => setOpen(false)}><X className="size-4" /></button></div>
    <div className="flex-1 space-y-3 overflow-y-auto p-4 text-sm" aria-live="polite">{msgs.map((m, i) => <div key={i} className={cn("max-w-[85%] rounded-xl px-3 py-2", m.role === "user" ? "ms-auto bg-primary text-primary-foreground" : "bg-muted")}>
      <div className="whitespace-pre-wrap">{m.content}</div>
      {m.sources?.length > 0 && <div className="mt-2 space-y-1">{m.sources.map((s: any) => <button key={s.id} onClick={() => { setOpen(false); nav(`/knowledge/${s.id}`); }} className="flex items-center gap-1 text-xs text-primary hover:underline"><BookOpen className="size-3" />{s.title}</button>)}</div>}
      {m.actions?.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{m.actions.map((a: any, k: number) => <Button key={k} size="sm" variant="outline" className="h-7 text-xs" onClick={() => act(a)}>{a.label}</Button>)}</div>}
      {m.engine && <div className="mt-1 text-[10px] text-muted-foreground">{m.engine === "llm" ? "AI answer" : "Answered with rules"}</div>}</div>)}
      {busy && <div className="text-xs text-muted-foreground">Thinking…</div>}</div>
    <div className="flex gap-2 border-t p-3"><input className="input h-9 flex-1" aria-label="Your question" placeholder="Ask a question…" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask()} /><Button size="sm" onClick={ask} disabled={busy} aria-label="Send"><Send /></Button></div>
  </div>;
}

export function TicketAI({ module, id, onPosted }: { module: string; id: number; onPosted: () => void }) {
  const [sum, setSum] = useState<string>(""); const [draft, setDraft] = useState(""); const [sim, setSim] = useState<any[] | null>(null); const [eng, setEng] = useState("");
  const err = (x: any) => toast.error(errMsg(x));
  const summarise = () => api.post(`/ai/tickets/${module}/${id}/summary`).then((r) => { setSum(r.data.summary); setEng(r.data.engine); }).catch(err);
  const reply = () => api.post(`/ai/tickets/${module}/${id}/reply`).then((r) => setDraft(r.data.reply)).catch(err);
  const similar = () => api.get(`/ai/tickets/${module}/${id}/similar`).then((r) => setSim(r.data)).catch(err);
  const polish = (mode: string) => api.post("/ai/write", { text: draft, mode }).then((r) => setDraft(r.data.text)).catch(err);
  const post = () => api.post(`/records/${module}/${id}/comments`, { body: draft }).then(() => { setDraft(""); toast.success("Reply posted"); onPosted(); }).catch(err);
  return <Card><CardHeader><CardTitle className="flex items-center gap-2"><Sparkles className="size-4 text-primary" />Neurealm AI helpers{eng && <Badge>{eng === "llm" ? "AI" : "rules"}</Badge>}</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
    <div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={summarise}>Summarise</Button><Button size="sm" variant="outline" onClick={reply}>Draft a reply</Button><Button size="sm" variant="outline" onClick={similar}>Find similar</Button></div>
    {sum && <div className="whitespace-pre-wrap rounded-lg bg-muted/60 p-3">{sum}</div>}
    {sim && (sim.length ? <ul className="space-y-1">{sim.map((s) => <li key={s.id}><a className="text-primary hover:underline" href={`/${module === "incident" ? "incidents" : module + "s"}/${s.id}`}>{s.number}</a> {s.title} <span className="text-xs text-muted-foreground">({s.state})</span></li>)}</ul> : <p className="text-muted-foreground">No similar tickets found.</p>)}
    {(draft || sum) && <div className="space-y-2"><Textarea rows={5} aria-label="Reply draft" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Write or draft a reply…" />
      <div className="flex flex-wrap gap-1.5">{["improve", "shorten", "friendly", "formal"].map((m) => <Button key={m} size="sm" variant="ghost" className="capitalize" disabled={!draft} onClick={() => polish(m)}>{m}</Button>)}
        <Button size="sm" variant="ghost" disabled={!draft} onClick={() => { navigator.clipboard?.writeText(draft); toast.success("Copied"); }}><Copy />Copy</Button><Button size="sm" className="ms-auto" disabled={!draft} onClick={post}>Post reply</Button></div></div>}
  </CardContent></Card>;
}
