import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, SlidersHorizontal, Trash2 } from "lucide-react";
import { api, errMsg } from "../api";
import { Page } from "../ui";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect, Label } from "@/components/ui/input";

const LV = ["High", "Medium", "Low"];
export default function TicketSettings() {
  const [c, setC] = useState<any>(null); const [cat, setCat] = useState("");
  useEffect(() => { api.get("/ticketing/config").then((r) => setC(r.data)); }, []);
  const save = async (body: any, ok = "Saved") => { try { setC((await api.put("/ticketing/config", body)).data); toast.success(ok); } catch (x) { toast.error(errMsg(x)); } };
  if (!c) return null;
  return <Page title="Ticket settings" icon={SlidersHorizontal} subtitle="Categories, custom fields, the priority matrix, quick replies and notification wording.">
    <div className="grid gap-4 lg:grid-cols-2">
      <Card><CardHeader><div><CardTitle>Categories</CardTitle><CardDescription>Used to sort and route tickets.</CardDescription></div></CardHeader><CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2">{c.categories.map((k: string) => <span key={k} className="inline-flex items-center gap-1 rounded-full border bg-card px-3 py-1 text-sm">{k}<button aria-label={`Remove ${k}`} onClick={() => save({ categories: c.categories.filter((x: string) => x !== k) }, "Category removed")}><Trash2 className="size-3 text-muted-foreground hover:text-red-600" /></button></span>)}</div>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); save({ categories: [...c.categories, cat] }, "Category added").then(() => setCat("")); }}><Input aria-label="New category" placeholder="New category" value={cat} onChange={(e) => setCat(e.target.value)} /><Button size="sm" disabled={!cat.trim()}><Plus />Add</Button></form></CardContent></Card>
      <Card><CardHeader><div><CardTitle>Priority matrix</CardTitle><CardDescription>Priority picked automatically from impact and urgency.</CardDescription></div></CardHeader><CardContent>
        <table className="w-full text-sm"><thead><tr><th className="th">Impact ↓ / Urgency →</th>{LV.map((l) => <th key={l} className="th">{l}</th>)}</tr></thead><tbody>{[1, 2, 3].map((i) => <tr key={i}><td className="td font-medium">{LV[i - 1]}</td>{[1, 2, 3].map((j) =>
          <td key={j} className="td"><NativeSelect aria-label={`Impact ${LV[i - 1]}, urgency ${LV[j - 1]}`} className="h-8" value={c.matrix[`${i},${j}`]} onChange={(e) => save({ matrix: { ...c.matrix, [`${i},${j}`]: e.target.value } }, "Matrix updated")}>{["P1", "P2", "P3", "P4"].map((p) => <option key={p}>{p}</option>)}</NativeSelect></td>)}</tr>)}</tbody></table></CardContent></Card>
      <Card><CardHeader><div><CardTitle>Custom fields</CardTitle><CardDescription>Custom fields now live in the Form designer, for every module.</CardDescription></div></CardHeader><CardContent><a className="text-sm font-medium text-primary hover:underline" href="/admin/forms">Open the Form designer →</a></CardContent></Card>
      <Card><CardHeader><div><CardTitle>Quick replies</CardTitle><CardDescription>Ready-made answers agents can send in one click.</CardDescription></div></CardHeader><CardContent className="space-y-2">
        {c.canned.map((k: any, i: number) => <div key={i} className="grid grid-cols-[160px_1fr_auto] gap-2"><Input aria-label="Reply title" defaultValue={k.title} onBlur={(e) => { const n = [...c.canned]; n[i] = { ...k, title: e.target.value }; save({ canned: n }); }} />
          <Input aria-label="Reply text" defaultValue={k.body} onBlur={(e) => { const n = [...c.canned]; n[i] = { ...k, body: e.target.value }; save({ canned: n }); }} />
          <Button size="sm" variant="ghost" aria-label="Remove reply" onClick={() => save({ canned: c.canned.filter((_: any, j: number) => j !== i) }, "Reply removed")}><Trash2 /></Button></div>)}
        <Button size="sm" variant="outline" onClick={() => save({ canned: [...c.canned, { title: "New reply", body: "Thanks! We're on it." }] }, "Reply added")}><Plus />Add reply</Button></CardContent></Card>
      <Card className="lg:col-span-2"><CardHeader><div><CardTitle>Notification wording</CardTitle><CardDescription>Use {"{number}"}, {"{title}"}, {"{state}"} and {"{priority}"}.</CardDescription></div></CardHeader><CardContent className="grid gap-3 md:grid-cols-3">
        {Object.entries(c.templates).map(([k, v]) => <div key={k}><Label htmlFor={`t-${k}`} className="capitalize">When {k}</Label><Input id={`t-${k}`} defaultValue={v as string} onBlur={(e) => e.target.value !== v && save({ templates: { ...c.templates, [k]: e.target.value } }, "Wording saved")} /></div>)}</CardContent></Card>
    </div>
  </Page>;
}
