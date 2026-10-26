import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Ban, CheckSquare, Copy, Eye, EyeOff, GitMerge, History, ListTodo, MessageSquareText, Square } from "lucide-react";
import { api, errMsg, type User } from "../api";
import { useAuth } from "../auth";
import { fmt } from "../ui";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/menu";

const ROUTE: Record<string, string> = { incident: "/incidents", problem: "/problems", change: "/changes", request: "/requests" };
const path = (m: string, id: number) => `${ROUTE[m] || `/m/${m}`}/${id}`;

export function TicketTools({ module, r, setR, staff, users, reload }: { module: string; r: any; setR: (x: any) => void; staff: boolean; users: User[]; reload: () => void }) {
  const { user } = useAuth();
  const [task, setTask] = useState(""); const [dups, setDups] = useState<any[]>([]); const [canned, setCanned] = useState<any[]>([]);
  const [hist, setHist] = useState<any[] | null>(null); const [into, setInto] = useState("");
  useEffect(() => { if (staff) { api.get(`/records/${module}/${r.id}/duplicates`).then((x) => setDups(x.data)).catch(() => {}); api.get("/ticketing/config").then((x) => setCanned(x.data.canned)); } }, [r.id]);
  const call = async (fn: () => Promise<any>, ok?: string) => { try { const x = await fn(); if (x?.data?.id === r.id) setR(x.data); if (ok) toast.success(ok); return x; } catch (e) { toast.error(errMsg(e)); } };
  const tasks: any[] = r.data?.tasks || []; const watchers: number[] = r.data?.watchers || []; const watching = !!user && watchers.includes(user.id);
  const uname = (id: number) => users.find((u) => u.id === id)?.full_name || "Someone";
  return <>
    {r.data?.merged_into && <Card className="border-nr-orange/40 bg-orange-50"><CardContent className="pt-5 text-sm">This ticket was merged into <b>{r.data.merged_into}</b>. Updates continue there.</CardContent></Card>}
    {staff && <Card><CardHeader><CardTitle className="flex items-center gap-2"><ListTodo className="size-4 text-muted-foreground" />Tasks<Badge className="px-1">{tasks.filter((t) => t.done).length}/{tasks.length}</Badge></CardTitle></CardHeader>
      <CardContent className="space-y-2 text-sm">
        {tasks.map((t) => <button key={t.id} className="flex w-full items-center gap-2 rounded-md px-1 py-1 text-start hover:bg-muted/50" onClick={() => call(() => api.post(`/records/${module}/${r.id}/tasks/${t.id}/toggle`))}>
          {t.done ? <CheckSquare className="size-4 text-primary" /> : <Square className="size-4 text-muted-foreground" />}<span className={t.done ? "text-muted-foreground line-through" : ""}>{t.title}</span></button>)}
        <form className="flex gap-2" onSubmit={async (e) => { e.preventDefault(); if (await call(() => api.post(`/records/${module}/${r.id}/tasks`, { title: task }), "Task added")) setTask(""); }}>
          <Input aria-label="New task" placeholder="Add a task…" value={task} onChange={(e) => setTask(e.target.value)} className="h-8" /><Button size="sm" variant="outline" disabled={!task.trim()}>Add</Button></form>
      </CardContent></Card>}
    <Card><CardHeader><CardTitle className="flex items-center gap-2"><Eye className="size-4 text-muted-foreground" />Watchers</CardTitle>
      <Button size="sm" variant="outline" onClick={() => call(() => api.post(`/records/${module}/${r.id}/watch`, null, { params: { on: !watching } }), watching ? "You'll stop getting updates" : "You'll get updates on this ticket")}>{watching ? <><EyeOff />Unwatch</> : <><Eye />Watch</>}</Button></CardHeader>
      <CardContent className="text-sm text-muted-foreground">{watchers.length ? watchers.map(uname).join(", ") : "Nobody is watching yet."}</CardContent></Card>
    {staff && canned.length > 0 && <Card><CardHeader><CardTitle className="flex items-center gap-2"><MessageSquareText className="size-4 text-muted-foreground" />Quick replies</CardTitle></CardHeader>
      <CardContent className="flex flex-wrap gap-2">{canned.map((c) => <Button key={c.id} size="sm" variant="outline" title={c.body} onClick={async () => { await call(() => api.post(`/records/${module}/${r.id}/comments`, { body: c.body }), "Reply sent"); reload(); }}>{c.title}</Button>)}</CardContent></Card>}
    {staff && <Card><CardHeader><CardTitle className="flex items-center gap-2"><Copy className="size-4 text-muted-foreground" />Possible duplicates</CardTitle></CardHeader>
      <CardContent className="space-y-2 text-sm">
        {dups.length === 0 ? <div className="text-muted-foreground">No similar open tickets. Nice.</div> : dups.map((d) => <div key={d.id} className="flex items-center gap-2">
          <Link to={path(module, d.id)} className="font-mono text-xs text-primary">{d.number}</Link><span className="flex-1 truncate">{d.title}</span><Badge>{Math.round(d.score * 100)}%</Badge>
          <Button size="sm" variant="ghost" onClick={() => setInto(String(d.id))}>Merge</Button></div>)}
        <div className="flex gap-2 pt-1"><Button size="sm" variant="outline" onClick={() => setInto(into || " ")}><GitMerge />Merge into…</Button>
          <Button size="sm" variant="outline" onClick={() => call(() => api.post(`/records/${module}/${r.id}/spam`), "Marked as spam and closed")}><Ban />Spam</Button>
          <Button size="sm" variant="outline" onClick={async () => setHist((await api.get(`/records/${module}/${r.id}/history`)).data)}><History />History</Button></div>
      </CardContent></Card>}
    <Dialog open={!!into} onOpenChange={(o) => !o && setInto("")}><DialogContent className="max-w-md space-y-3 p-6"><DialogTitle className="text-lg font-semibold">Merge {r.number}</DialogTitle>
      <p className="text-sm text-muted-foreground">Replies and watchers move to the other ticket, and this one is closed with a note.</p>
      <NativeSelect value={into.trim()} onChange={(e) => setInto(e.target.value)}><option value="">Pick a ticket…</option>{dups.map((d) => <option key={d.id} value={d.id}>{d.number} · {d.title}</option>)}</NativeSelect>
      <Input placeholder="…or type a ticket ID" value={into.trim()} onChange={(e) => setInto(e.target.value.replace(/\D/g, "") || " ")} />
      <div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setInto("")}>Cancel</Button>
        <Button disabled={!into.trim()} onClick={async () => { const x = await call(() => api.post(`/records/${module}/${r.id}/merge`, { into: +into.trim() }), "Merged"); if (x) { setInto(""); reload(); } }}>Merge</Button></div></DialogContent></Dialog>
    <Dialog open={!!hist} onOpenChange={(o) => !o && setHist(null)}><DialogContent className="max-w-lg space-y-3 p-6"><DialogTitle className="text-lg font-semibold">History of {r.number}</DialogTitle>
      <ol className="max-h-[60vh] space-y-2 overflow-auto text-sm">{(hist || []).map((h, i) => <li key={i} className="rounded-md border p-2"><div className="flex justify-between"><b className="font-medium">{h.actor}</b><span className="text-xs text-muted-foreground">{fmt(h.ts)}</span></div>
        <div className="text-muted-foreground">{h.action.replace(".", " ")}{h.details && Object.keys(h.details).length > 0 && <> · {Object.entries(h.details).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(" → ") : String(v)}`).join(", ")}</>}</div></li>)}</ol></DialogContent></Dialog>
  </>;
}

/** Shown when someone else saved the ticket first (HTTP 409). */
export function ConflictDialog({ open, onReload, onClose }: { open: boolean; onReload: () => void; onClose: () => void }) {
  return <Dialog open={open} onOpenChange={(o) => !o && onClose()}><DialogContent className="max-w-md space-y-3 p-6"><DialogTitle className="text-lg font-semibold">This ticket just changed</DialogTitle>
    <p className="text-sm text-muted-foreground">Someone else updated this ticket while you were working on it. Load their changes first, then make yours again, so nothing gets overwritten.</p>
    <div className="flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Keep looking</Button><Button onClick={onReload}>Load latest</Button></div></DialogContent></Dialog>;
}
