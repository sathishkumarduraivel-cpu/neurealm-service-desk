import { useEffect, useState } from "react";
import { toast } from "sonner";
import { RotateCcw, Star } from "lucide-react";
import { api, errMsg } from "../api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const DONE = ["resolved", "closed", "fulfilled"];
export function RequesterFeedback({ r, me, module, onChange }: { r: any; me: any; module: string; onChange: () => void }) {
  const [score, setScore] = useState(0); const [c, setC] = useState(""); const [why, setWhy] = useState(""); const [reo, setReo] = useState(false);
  if (!me || r.requester?.id !== me.id || !DONE.includes(r.state)) return null;
  const done = r.data?.csat;
  const rate = () => api.post(`/records/${module}/${r.id}/rate`, { score, comment: c }).then(() => { toast.success("Thank you for your feedback!"); onChange(); }).catch((x) => toast.error(errMsg(x)));
  const reopen = () => api.post(`/records/${module}/${r.id}/reopen`, { reason: why }).then(() => { toast.success("Reopened. We're on it again."); onChange(); }).catch((x) => toast.error(errMsg(x)));
  return <Card><CardHeader><CardTitle>How did we do?</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
    {done ? <p className="text-muted-foreground">You rated this {done.score}/5. Thanks!</p> : <>
      <div className="flex gap-1" role="radiogroup" aria-label="Rating">{[1, 2, 3, 4, 5].map((n) => <button key={n} aria-label={`${n} stars`} onClick={() => setScore(n)}><Star className={cn("size-6", n <= score ? "fill-amber-400 text-amber-400" : "text-muted-foreground")} /></button>)}</div>
      <Textarea rows={2} placeholder="Anything we could do better? (optional)" value={c} onChange={(e) => setC(e.target.value)} />
      <Button size="sm" disabled={!score} onClick={rate}>Send rating</Button></>}
    <div className="border-t pt-3">{!reo ? <Button size="sm" variant="outline" onClick={() => setReo(true)}><RotateCcw />Not fixed? Reopen</Button> : <div className="space-y-2">
      <Textarea rows={2} placeholder="What's still not working?" value={why} onChange={(e) => setWhy(e.target.value)} />
      <div className="flex gap-2"><Button size="sm" disabled={!why.trim()} onClick={reopen}>Reopen</Button><Button size="sm" variant="ghost" onClick={() => setReo(false)}>Cancel</Button></div></div>}</div>
  </CardContent></Card>;
}

export function DelegateCard({ users }: { users: any[] }) {
  const [d, setD] = useState<any>(undefined);
  useEffect(() => { api.get("/me/delegate").then((r) => setD(r.data || {})).catch(() => setD({})); }, []);
  const save = (to: string, until: string) => api.put("/me/delegate", { to_user_id: to ? +to : null, until: until || null }).then((r) => { setD(r.data || {}); toast.success(to ? "Delegation saved" : "Delegation turned off"); }).catch((x) => toast.error(errMsg(x)));
  const [to, setTo] = useState(""); const [until, setUntil] = useState("");
  return <Card><CardHeader><CardTitle>Away? Delegate your approvals</CardTitle></CardHeader><CardContent className="flex flex-wrap items-end gap-2 text-sm">
    {d?.to ? <p className="w-full text-muted-foreground">Delegated to <b>{users.find((u) => u.id === d.to)?.full_name || `user ${d.to}`}</b>{d.until ? ` until ${d.until}` : ""}.</p> : <p className="w-full text-muted-foreground">Pick a colleague to approve on your behalf while you're away.</p>}
    <select className="input h-9 w-56" aria-label="Delegate" value={to} onChange={(e) => setTo(e.target.value)}><option value="">Nobody</option>{users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</select>
    <input type="date" className="input h-9 w-44" aria-label="Until" value={until} onChange={(e) => setUntil(e.target.value)} />
    <Button size="sm" onClick={() => save(to, until)}>Save</Button>{d?.to && <Button size="sm" variant="ghost" onClick={() => save("", "")}>Turn off</Button>}
  </CardContent></Card>;
}
