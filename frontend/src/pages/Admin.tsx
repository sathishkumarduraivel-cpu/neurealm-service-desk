import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { ShieldCheck, ShieldX, Settings, Timer, UserPlus, Users, ScrollText, ToggleRight, UsersRound, KeyRound, LogIn, Check } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { FEATURES } from "../nav";
import { useFeatures } from "../features";
import { api, errMsg, type Group, type User } from "../api";
import { Page, fmt } from "../ui";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { FieldError, Input, Label, NativeSelect } from "@/components/ui/input";
import { Person, Switch, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/misc";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/menu";
const schema = z.object({ full_name: z.string().trim().min(2, "Name is required"), email: z.string().trim().email("Valid email required"), password: z.string().min(8, "At least 8 characters"), role: z.enum(["admin", "agent", "end_user"]), group_id: z.string().optional() });
export default function Admin() {
  const [users, setUsers] = useState<User[]>([]); const [groups, setGroups] = useState<Group[]>([]); const [audit, setAudit] = useState<any[]>([]); const [chain, setChain] = useState<any>(null);
  const [sla, setSla] = useState<any[]>([]); const [open, setOpen] = useState(false);
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { role: "agent", group_id: "" } });
  const load = () => { api.get("/users").then((r) => setUsers(r.data)); api.get("/audit", { params: { limit: 25 } }).then((r) => setAudit(r.data)); api.get("/audit/verify").then((r) => setChain(r.data)); api.get("/sla/policies").then((r) => setSla(r.data)); };
  useEffect(() => { load(); api.get("/groups").then((r) => setGroups(r.data)); }, []);
  const add = async (f: z.infer<typeof schema>) => { try { await api.post("/users", { ...f, group_id: f.group_id ? +f.group_id : null }); toast.success(`${f.full_name} added`); reset(); setOpen(false); load(); } catch (x) { toast.error(errMsg(x)); } };
  const upd = async (id: number, body: any) => { try { await api.patch(`/users/${id}`, body); toast.success("User updated"); load(); } catch (x) { toast.error(errMsg(x)); } };
  const gname = (id: number | null) => groups.find((g) => g.id === id)?.name || "—";
  const roleTone = { admin: "violet", agent: "brand", end_user: "neutral" } as const;
  return (
    <Page title="Administration" icon={Settings} subtitle="Manage people, service levels and the tamper-evident audit trail.">
      <Tabs defaultValue="users"><TabsList><TabsTrigger value="users"><Users />Users<Badge className="px-1">{users.length}</Badge></TabsTrigger><TabsTrigger value="sla"><Timer />SLA policies</TabsTrigger><TabsTrigger value="audit"><ScrollText />Audit log</TabsTrigger><TabsTrigger value="groups"><UsersRound />Groups</TabsTrigger><TabsTrigger value="roles"><KeyRound />Roles</TabsTrigger><TabsTrigger value="signin"><LogIn />Sign-in</TabsTrigger><TabsTrigger value="features"><ToggleRight />Features</TabsTrigger></TabsList>
        <TabsContent value="groups"><GroupsTab groups={groups} users={users} reload={() => api.get("/groups").then((r) => setGroups(r.data))} /></TabsContent>
        <TabsContent value="roles"><RolesTab /></TabsContent>
        <TabsContent value="signin"><SignInTab /></TabsContent>
        <TabsContent value="features"><FeatureToggles /></TabsContent>
        <TabsContent value="users"><Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b px-4 py-3"><div className="text-sm text-muted-foreground">{users.filter((u) => u.active).length} active · {users.filter((u) => u.role === "admin").length} admins</div><Button size="sm" onClick={() => setOpen(true)}><UserPlus />Add user</Button></div>
          <table className="w-full"><thead><tr>{["Name", "Email", "Role", "Group", "Active", ""].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
            <tbody>{users.map((u) => <tr key={u.id}><td className="td"><Person name={u.full_name} /></td><td className="td text-muted-foreground">{u.email}</td>
              <td className="td"><div className="flex items-center gap-2"><Badge tone={roleTone[u.role]} className="capitalize">{u.role.replace("_", " ")}</Badge><NativeSelect className="h-7 w-[110px] text-xs" value={u.role} onChange={(e) => upd(u.id, { role: e.target.value })}><option value="admin">Admin</option><option value="agent">Agent</option><option value="end_user">End user</option></NativeSelect></div></td>
              <td className="td text-muted-foreground">{gname(u.group_id)}</td><td className="td"><Switch checked={u.active} onCheckedChange={(v) => upd(u.id, { active: v })} /></td><td className="td text-end whitespace-nowrap"><UserActions u={u} /></td></tr>)}</tbody></table></Card></TabsContent>
        <TabsContent value="sla"><Card className="overflow-hidden"><table className="w-full"><thead><tr>{["Policy", "Priority", "Response target", "Resolution target"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody>{sla.map((p) => <tr key={p.id}><td className="td font-medium">{p.name}</td><td className="td"><Badge tone={p.priority === "P1" ? "red" : p.priority === "P2" ? "orange" : p.priority === "P3" ? "amber" : "neutral"}>{p.priority}</Badge></td><td className="td tabular-nums">{p.response_minutes} min</td><td className="td tabular-nums">{(p.resolution_minutes / 60).toFixed(1)} h</td></tr>)}</tbody></table></Card></TabsContent>
        <TabsContent value="audit"><Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b px-4 py-3"><div><div className="text-sm font-medium">Hash-chained audit log</div><div className="text-xs text-muted-foreground">Every change is SHA-256 chained to the previous entry.</div></div>
            {chain && (chain.valid ? <Badge tone="green" className="py-1"><ShieldCheck className="size-3.5" />Chain verified · {chain.entries} entries</Badge> : <Badge tone="red" className="py-1"><ShieldX className="size-3.5" />Broken at #{chain.broken_at}</Badge>)}</div>
          <table className="w-full"><thead><tr>{["Time", "Action", "Entity", "Hash"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
            <tbody>{audit.map((a) => <tr key={a.id}><td className="td whitespace-nowrap text-xs text-muted-foreground">{fmt(a.ts)}</td><td className="td"><Badge>{a.action}</Badge></td><td className="td">{a.entity} <span className="text-muted-foreground">#{a.entity_id}</span></td><td className="td font-mono text-xs text-muted-foreground">{a.hash.slice(0, 16)}…</td></tr>)}</tbody></table></Card></TabsContent>
      </Tabs>
      <Dialog open={open} onOpenChange={setOpen}><DialogContent><form onSubmit={handleSubmit(add)}>
        <div className="border-b p-5"><DialogTitle className="text-base font-semibold">Add user</DialogTitle><p className="mt-0.5 text-sm text-muted-foreground">They can sign in immediately with these credentials.</p></div>
        <div className="grid gap-4 p-5 sm:grid-cols-2">
          <div className="sm:col-span-2"><Label>Full name</Label><Input aria-label="Full name" {...register("full_name")} /><FieldError msg={errors.full_name?.message} /></div>
          <div><Label>Email</Label><Input aria-label="Email" {...register("email")} /><FieldError msg={errors.email?.message} /></div>
          <div><Label>Temporary password</Label><Input aria-label="Temporary password" type="password" {...register("password")} /><FieldError msg={errors.password?.message} /></div>
          <div><Label>Role</Label><NativeSelect aria-label="Role" {...register("role")}><option value="admin">Admin</option><option value="agent">Agent</option><option value="end_user">End user</option></NativeSelect></div>
          <div><Label>Group</Label><NativeSelect aria-label="Group" {...register("group_id")}><option value="">No group</option>{groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</NativeSelect></div></div>
        <div className="flex justify-end gap-2 border-t bg-muted/30 px-5 py-3"><Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button disabled={isSubmitting}>Add user</Button></div></form></DialogContent></Dialog>
    </Page>
  );
}

function FeatureToggles() {
  const { features, save } = useFeatures();
  const flip = async (k: string, v: boolean) => { try { await save({ ...features, [k]: v }); toast.success(v ? "Turned on. It now shows in the sidebar." : "Turned off."); } catch (x) { toast.error(errMsg(x)); } };
  return <Card className="divide-y">
    <div className="p-4 text-sm text-muted-foreground">These extra modules are off by default. Switch on the ones your team needs and they will appear under “More modules”.</div>
    {FEATURES.map((f) => { const k = f.key; return <div key={k} className="flex items-center justify-between gap-4 p-4">
      <div><div className="font-medium">{f.label}</div><div className="text-xs text-muted-foreground">{f.hint}</div></div>
      <Switch aria-label={f.label} checked={!!features[k]} onCheckedChange={(v) => flip(k, v)} /></div>; })}
  </Card>;
}

function UserActions({ u }: { u: User }) {
  const { user, impersonate } = useAuth(); const nav = useNavigate();
  if (!user || u.id === user.id) return null;
  return <div className="flex justify-end gap-1">
    <Button size="sm" variant="ghost" disabled={!u.active} onClick={async () => { try { const x = await impersonate(u.id); toast.success(`You are now viewing Neurealm Service Desk as ${x.full_name}`); nav(x.role === "end_user" ? "/portal" : "/dashboard"); } catch (e) { toast.error(errMsg(e)); } }}>Sign in as</Button>
    <Button size="sm" variant="ghost" onClick={async () => { try { await api.post(`/admin/users/${u.id}/reset-2fa`); toast.success("Two-step sign-in reset"); } catch (e) { toast.error(errMsg(e)); } }}>Reset 2FA</Button>
  </div>;
}

function GroupsTab({ groups, users, reload }: { groups: Group[]; users: User[]; reload: () => void }) {
  const [f, setF] = useState({ name: "", description: "" });
  const add = async (e: React.FormEvent) => { e.preventDefault(); try { await api.post("/admin/groups", f); toast.success("Group created"); setF({ name: "", description: "" }); reload(); } catch (x) { toast.error(errMsg(x)); } };
  return <Card className="overflow-hidden">
    <form onSubmit={add} className="flex flex-wrap items-end gap-2 border-b px-4 py-3"><div><Label htmlFor="gn">Group name</Label><Input id="gn" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
      <div className="flex-1"><Label htmlFor="gd">Description</Label><Input id="gd" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></div><Button size="sm" disabled={f.name.trim().length < 2}><UsersRound />Add group</Button></form>
    <table className="w-full"><thead><tr>{["Group", "Description", "Members"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
      <tbody>{groups.map((g) => <tr key={g.id}><td className="td font-medium">{g.name}</td><td className="td text-muted-foreground">{(g as any).description || "—"}</td><td className="td tabular-nums">{users.filter((u) => u.group_id === g.id).length}</td></tr>)}</tbody></table></Card>;
}

function RolesTab() {
  const [d, setD] = useState<{ roles: { key: string; label: string; hint: string }[]; permissions: { key: string; label: string; roles: string[] }[] } | null>(null);
  useEffect(() => { api.get("/roles").then((r) => setD(r.data)); }, []);
  if (!d) return null;
  return <Card className="overflow-hidden"><div className="border-b px-4 py-3 text-sm text-muted-foreground">What each role can do in Neurealm Service Desk.</div>
    <table className="w-full"><thead><tr><th className="th">Permission</th>{d.roles.map((r) => <th key={r.key} className="th text-center" title={r.hint}>{r.label}</th>)}</tr></thead>
      <tbody>{d.permissions.map((p) => <tr key={p.key}><td className="td">{p.label}</td>{d.roles.map((r) => <td key={r.key} className="td text-center">{p.roles.includes(r.key) ? <Check className="mx-auto size-4 text-primary" aria-label="Allowed" /> : <span className="text-muted-foreground/40">—</span>}</td>)}</tr>)}</tbody></table></Card>;
}

function SignInTab() {
  const [s, setS] = useState<{ registration: boolean; require_2fa_admins: boolean } | null>(null);
  useEffect(() => { api.get("/admin/auth-settings").then((r) => setS(r.data)); }, []);
  const save = async (k: string, v: boolean) => { try { setS((await api.put("/admin/auth-settings", { [k]: v })).data); toast.success("Saved"); } catch (x) { toast.error(errMsg(x)); } };
  if (!s) return null;
  const rows: [keyof typeof s, string, string][] = [["registration", "Allow self sign-up", "People with a company email can create an employee account."], ["require_2fa_admins", "Encourage two-step sign-in for admins", "Admins see a reminder until they turn it on."]];
  return <Card className="divide-y">{rows.map(([k, l, h]) => <div key={k} className="flex items-center justify-between gap-4 p-4"><div><div className="font-medium">{l}</div><div className="text-xs text-muted-foreground">{h}</div></div><Switch aria-label={l} checked={!!s[k]} onCheckedChange={(v) => save(k, v)} /></div>)}
    <div className="p-4 text-sm text-muted-foreground">Single sign-on with Microsoft or Google can be connected under Integrations.</div></Card>;
}
