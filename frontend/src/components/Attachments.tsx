import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Paperclip, Trash2, Upload } from "lucide-react";
import { api, errMsg } from "../api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const kb = (n: number) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
export function Attachments({ module, id, staff }: { module: string; id: number; staff: boolean }) {
  const [list, setList] = useState<any[]>([]); const ref = useRef<HTMLInputElement>(null); const [busy, setBusy] = useState(false);
  const load = () => api.get(`/records/${module}/${id}/attachments`).then((r) => setList(r.data)).catch(() => {});
  useEffect(() => { load(); }, [module, id]);
  const up = async (files: FileList | null) => { if (!files?.length) return; setBusy(true);
    for (const f of Array.from(files)) { const fd = new FormData(); fd.append("file", f); try { await api.post(`/records/${module}/${id}/attachments`, fd); } catch (x) { toast.error(`Couldn't attach ${f.name}`, { description: errMsg(x) }); } }
    setBusy(false); load(); };
  const dl = async (a: any) => { const r = await api.get(`/attachments/${a.id}`, { responseType: "blob" }); const l = document.createElement("a"); l.href = URL.createObjectURL(r.data); l.download = a.filename; l.click(); };
  return <Card onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); up(e.dataTransfer.files); }}>
    <CardHeader className="flex-row items-center justify-between"><CardTitle>Attachments</CardTitle>
      <Button size="sm" variant="outline" disabled={busy} onClick={() => ref.current?.click()}><Upload />{busy ? "Uploading…" : "Attach"}</Button>
      <input ref={ref} type="file" multiple hidden onChange={(e) => up(e.target.files)} /></CardHeader>
    <CardContent>{!list.length ? <p className="text-sm text-muted-foreground">Drop files here, up to 5 MB each.</p> :
      <ul className="divide-y rounded-lg border text-sm">{list.map((a) => <li key={a.id} className="flex items-center gap-2 px-3 py-2"><Paperclip className="size-4 text-muted-foreground" />
        <button className="flex-1 truncate text-start text-primary hover:underline" onClick={() => dl(a)}>{a.filename}</button><span className="text-xs text-muted-foreground">{kb(a.size)}</span>
        {staff && <button aria-label={`Remove ${a.filename}`} onClick={async () => { await api.delete(`/attachments/${a.id}`); load(); }}><Trash2 className="size-4 text-muted-foreground" /></button>}</li>)}</ul>}</CardContent></Card>;
}
