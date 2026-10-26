import { useEffect, useState } from "react";
import { api, errMsg } from "../api";
import { useAuth } from "../auth";
import { Page, fmt, Ico } from "../ui";
const SN = JSON.stringify({ table: "incident", dry_run: true, records: [{ number: "INC0099001", short_description: "Legacy: Citrix session freezes", state: "2", priority: "2", impact: "2", urgency: "2", assignment_group: "Application Support", sys_created_on: "2026-09-12 09:30:00" }, { number: "INC0099002", short_description: "Legacy: keyboard replacement", state: "7", priority: "4", close_notes: "Replaced keyboard" }] }, null, 2);
export default function Integrations() {
  const { user } = useAuth(); const [ad, setAd] = useState<any[]>([]); const [cs, setCs] = useState<any[]>([]); const [logs, setLogs] = useState<any[]>([]); const [sn, setSn] = useState(SN); const [res, setRes] = useState<any>(null);
  const load = () => { api.get("/integrations/connectors").then((r) => setCs(r.data)); api.get("/integrations/logs").then((r) => setLogs(r.data)); };
  useEffect(() => { api.get("/integrations/adapters").then((r) => setAd(r.data)); load(); }, []);
  const toggle = async (c: any) => { await api.patch(`/integrations/connectors/${c.id}`, { enabled: !c.enabled }); load(); };
  const test = async (c: any) => { await api.post(`/integrations/connectors/${c.id}/test`); load(); };
  const imp = async () => { try { setRes((await api.post("/integrations/servicenow/import", JSON.parse(sn))).data); } catch (x) { setRes({ error: errMsg(x) }); } };
  const isAdmin = user?.role === "admin";
  return (
    <Page title="Integration Hub">
      <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">{ad.map((a) => { const c = cs.find((x) => x.kind === a.kind); return (
        <div key={a.kind} className="card p-3 text-sm"><div className="flex justify-between"><b>{a.label}</b><span className="text-[10px] uppercase text-slate-400">{a.direction}</span></div><div className="text-xs text-slate-500 h-10 overflow-hidden">{a.description}</div>
          {c ? <div className="flex gap-2 mt-2 items-center"><span className={`w-2 h-2 rounded-full ${c.enabled ? "bg-emerald-500" : "bg-slate-300"}`} /><span className="text-xs flex-1 truncate">{c.name}</span>{isAdmin && <button className="text-xs underline" onClick={() => toggle(c)}>{c.enabled ? "disable" : "enable"}</button>}{a.direction !== "in" && <button className="text-xs underline" onClick={() => test(c)}>test</button>}</div> : <div className="text-xs text-slate-400 mt-2">not configured</div>}</div>); })}</div>
      <div className="card p-4 text-xs text-slate-600">Inbound webhooks: <code className="bg-slate-100 px-1">POST /api/integrations/&lt;kind&gt;/webhook</code> signed with <code className="bg-slate-100 px-1">X-Neurealm Service Desk-Signature: HMAC-SHA256(secret, body)</code> or <code className="bg-slate-100 px-1">?token=&lt;secret&gt;</code>. Outbound deliveries are POSTed to the connector URL, or logged as <i>simulated</i> when no URL is set (air-gapped/demo).</div>
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="card overflow-hidden"><div className="px-4 py-3 font-semibold">Delivery log</div><div className="max-h-[420px] overflow-y-auto"><table className="w-full"><tbody>{logs.map((l) => <tr key={l.id}><td className="td text-xs">{fmt(l.created_at)}</td><td className="td text-xs">{l.direction === "out" ? <Ico n="up" className="me-1 text-indigo-500" /> : <Ico n="down" className="me-1 text-emerald-500" />}{l.connector}</td><td className="td text-xs">{l.status}</td>
          <td className="td text-[10px] font-mono text-slate-500 max-w-[260px] truncate">{JSON.stringify(l.payload)}</td></tr>)}</tbody></table></div></div>
        <div className="card p-4 space-y-2"><h3 className="font-semibold">ServiceNow migration import {!isAdmin && <span className="text-xs text-slate-400">(admin only)</span>}</h3><p className="text-xs text-slate-500">Tables: incident, problem, change_request, sc_req_item, kb_knowledge. States, priorities and groups are mapped and SN numbers preserved; re-running the import skips records already migrated.</p>
          <textarea className="input font-mono text-xs h-52" value={sn} onChange={(e) => setSn(e.target.value)} /><button className="btn" onClick={imp} disabled={!isAdmin}>Run import</button>
          {res && <pre className="text-xs bg-slate-50 p-2 rounded max-h-40 overflow-auto">{JSON.stringify(res, null, 2)}</pre>}</div>
      </div>
    </Page>
  );
}
