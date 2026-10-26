import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, errMsg } from "../api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, NativeSelect, Textarea } from "@/components/ui/input";
import { fmt } from "../ui";

export function ItsmPanels({ r, module, staff, onChange }: { r: any; module: string; staff: boolean; onChange: () => void }) {
  if (!staff) return null;
  if (module === "change") return <><RiskCard r={r} onChange={onChange} />{["implement", "review", "closed"].includes(r.state) && <PirCard r={r} onChange={onChange} />}</>;
  if (module === "problem") return <RcaCard r={r} onChange={onChange} />;
  if (module === "incident") return <MajorCard r={r} onChange={onChange} />;
  return null;
}
const err = (x: any) => toast.error(errMsg(x));

function RiskCard({ r, onChange }: any) {
  const [qs, setQs] = useState<any[]>([]); const [a, setA] = useState<any>(r.data?.risk_answers || {});
  useEffect(() => { api.get("/change-ops/config").then((x) => setQs(x.data.questions)); }, []);
  const save = () => api.post(`/changes/${r.id}/risk`, a).then((x) => { toast.success(`Risk: ${x.data.risk_level} (${x.data.risk_score})`); onChange(); }).catch(err);
  return <Card><CardHeader><CardTitle>Risk assessment <Badge className="ms-2" tone={r.data?.risk_level === "high" ? "red" : r.data?.risk_level === "moderate" ? "amber" : "green"}>{r.data?.risk_level || "not assessed"}</Badge></CardTitle></CardHeader>
    <CardContent className="space-y-2 text-sm">{qs.map((q) => <label key={q.key} className="flex items-center gap-2"><input type="checkbox" checked={!!a[q.key]} onChange={(e) => setA({ ...a, [q.key]: e.target.checked })} />{q.label}</label>)}
      <Button size="sm" onClick={save}>Save assessment</Button></CardContent></Card>;
}
function PirCard({ r, onChange }: any) {
  const p = r.data?.pir; const [ok, setOk] = useState(true); const [n, setN] = useState(""); const [l, setL] = useState("");
  if (p) return <Card><CardHeader><CardTitle>Post-implementation review</CardTitle></CardHeader><CardContent className="text-sm"><Badge tone={p.successful ? "green" : "red"}>{p.successful ? "Successful" : "Had issues"}</Badge><p className="mt-2">{p.notes}</p>{p.lessons && <p className="mt-1 text-muted-foreground">Lessons: {p.lessons}</p>}<p className="mt-1 text-xs text-muted-foreground">{p.by} · {fmt(p.at)}</p></CardContent></Card>;
  return <Card><CardHeader><CardTitle>Post-implementation review</CardTitle></CardHeader><CardContent className="space-y-2 text-sm">
    <NativeSelect value={ok ? "1" : "0"} onChange={(e) => setOk(e.target.value === "1")}><option value="1">It went as planned</option><option value="0">There were issues</option></NativeSelect>
    <Textarea rows={2} placeholder="What happened?" value={n} onChange={(e) => setN(e.target.value)} /><Textarea rows={2} placeholder="Lessons for next time" value={l} onChange={(e) => setL(e.target.value)} />
    <Button size="sm" onClick={() => api.post(`/changes/${r.id}/pir`, { successful: ok, notes: n, lessons: l }).then(() => { toast.success("Review saved"); onChange(); }).catch(err)}>Save review</Button></CardContent></Card>;
}
function RcaCard({ r, onChange }: any) {
  const x = r.data?.rca || {}; const [w, setW] = useState<string[]>(x.whys?.length ? x.whys : ["", "", ""]); const [rc, setRc] = useState(x.root_cause || r.data?.root_cause || "");
  return <Card><CardHeader><CardTitle>Root cause (5 whys)</CardTitle></CardHeader><CardContent className="space-y-2 text-sm">
    {w.map((v, i) => <div key={i}><Label>Why {i + 1}?</Label><Input value={v} onChange={(e) => setW(w.map((y, j) => j === i ? e.target.value : y))} /></div>)}
    {w.length < 5 && <Button size="sm" variant="ghost" onClick={() => setW([...w, ""])}>Ask another why</Button>}
    <div><Label>Root cause</Label><Textarea aria-label="Root cause" rows={2} value={rc} onChange={(e) => setRc(e.target.value)} /></div>
    <div className="flex gap-2"><Button size="sm" onClick={() => api.put(`/problems/${r.id}/rca`, { method: "5whys", whys: w.filter(Boolean), root_cause: rc }).then(() => { toast.success("Root cause saved"); onChange(); }).catch(err)}>Save</Button>
      <Button size="sm" variant="outline" onClick={() => api.post(`/records/problem/${r.id}/known-error`, { root_cause: rc, workaround: r.data?.workaround || "" }).then(() => { toast.success("Published as a known error"); onChange(); }).catch(err)}>Mark known error</Button></div></CardContent></Card>;
}
function MajorCard({ r, onChange }: any) {
  const d = r.data || {}; const [msg, setMsg] = useState(""); const [aud, setAud] = useState("everyone"); const [sum, setSum] = useState(""); const [rc, setRc] = useState("");
  if (!d.major) return <Card><CardContent className="flex items-center justify-between gap-2 pt-5 text-sm"><span className="text-muted-foreground">Affecting lots of people?</span><Button size="sm" variant="destructive" onClick={() => api.post(`/incidents/${r.id}/major`, { declare: true }).then(() => { toast.success("Major incident declared"); onChange(); }).catch(err)}>Declare major incident</Button></CardContent></Card>;
  return <Card className="border-red-200"><CardHeader><CardTitle className="flex items-center gap-2"><Badge tone="red">Major incident</Badge><span className="text-xs font-normal text-muted-foreground">since {fmt(d.major_at)}</span></CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
    <div><Label>Send an update</Label><div className="flex gap-2"><NativeSelect aria-label="Audience" className="w-40" value={aud} onChange={(e) => setAud(e.target.value)}><option value="everyone">Everyone</option><option value="leadership">Leadership</option><option value="it">IT team</option></NativeSelect><Input value={msg} onChange={(e) => setMsg(e.target.value)} placeholder="What's the latest?" /></div>
      <Button size="sm" className="mt-2" onClick={() => api.post(`/incidents/${r.id}/comms`, { audience: aud, message: msg }).then(() => { setMsg(""); toast.success("Update sent"); onChange(); }).catch(err)}>Send update</Button></div>
    {(d.comms || []).length > 0 && <ul className="space-y-1 border-s-2 ps-3">{[...d.comms].reverse().map((c: any, i: number) => <li key={i}><span className="text-xs text-muted-foreground">{fmt(c.at)} · {c.by} → {c.audience}</span><div>{c.message}</div></li>)}</ul>}
    {d.review ? <div className="rounded-lg bg-muted/50 p-3"><div className="font-medium">Review</div><p>{d.review.summary}</p></div> : <div className="space-y-2 border-t pt-3"><Label>Major incident review</Label>
      <Textarea rows={2} placeholder="What happened and how we fixed it" value={sum} onChange={(e) => setSum(e.target.value)} /><Input placeholder="Root cause (if known)" value={rc} onChange={(e) => setRc(e.target.value)} />
      <Button size="sm" variant="outline" onClick={() => api.post(`/incidents/${r.id}/major-review`, { summary: sum, root_cause: rc, problem: true }).then(() => { toast.success("Review saved and a problem record opened"); onChange(); }).catch(err)}>Save review & open problem</Button></div>}
  </CardContent></Card>;
}
