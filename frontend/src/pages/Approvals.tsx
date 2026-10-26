import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Check, CheckSquare, X } from "lucide-react";
import { api, errMsg } from "../api";
import { Page, Priority } from "../ui";
import { ROUTE } from "./Records";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState, Skeleton } from "@/components/ui/misc";
import { humanize } from "@/lib/utils";
import { DelegateCard } from "@/components/Feedback";
import { useAuth } from "../auth";
export default function Approvals() {
  const [rows, setRows] = useState<any[] | null>(null);
  const load = () => api.get("/approvals/pending").then((r) => setRows(r.data));
  const [users, setUsers] = useState<any[]>([]); const { user } = useAuth();
  useEffect(() => { load(); api.get("/users").then((r) => setUsers(r.data.filter((x: any) => x.role !== "end_user" && x.id !== user?.id))); }, []);
  const decide = async (id: number, approve: boolean, n: string) => { try { await api.post(`/approvals/${id}/decide`, { approve }); toast.success(`${n} ${approve ? "approved" : "rejected"}`); load(); } catch (x) { toast.error(errMsg(x)); } };
  return (
    <Page title="Approvals" icon={CheckSquare} subtitle={rows ? `${rows.length} awaiting your decision` : "Loading…"}>
      <div className="overflow-hidden rounded-lg border bg-card shadow-xs">
        {rows === null ? <div className="space-y-3 p-4">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-14" />)}</div> : !rows.length ? <EmptyState icon={Check} title="Nothing pending" desc="You're all caught up on approvals." /> :
          <ul className="divide-y">{rows.map((a) => <li key={a.approval_id} className="flex flex-wrap items-center gap-4 px-5 py-4">
            <div className="min-w-0 flex-1"><div className="flex items-center gap-2"><Link className="font-mono text-xs font-medium text-primary hover:underline" to={`/${ROUTE[a.record.module]}/${a.record.id}`}>{a.record.number}</Link><Priority p={a.record.priority} /><Badge>Level {a.level}</Badge></div>
              <div className="mt-1 truncate font-medium">{a.record.title}</div>
              <div className="mt-0.5 text-xs capitalize text-muted-foreground">{a.data.change_type ? <>{humanize(a.data.change_type)} change · risk <b className="text-foreground">{a.data.risk_score}</b> ({a.data.risk_level})</> : a.data.item}</div></div>
            <div className="flex gap-2"><Button variant="outline" size="sm" onClick={() => decide(a.approval_id, false, a.record.number)}><X />Reject</Button><Button size="sm" onClick={() => decide(a.approval_id, true, a.record.number)}><Check />Approve</Button></div></li>)}</ul>}
      </div>
      <DelegateCard users={users} />
    </Page>
  );
}
