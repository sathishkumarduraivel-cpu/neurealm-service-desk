import { useEffect, useState } from "react";
import { toast } from "sonner";
import { KeyRound, ShieldCheck, Trash2, UserCircle, Copy } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { api, errMsg } from "../api";
import { useAuth } from "../auth";
import { useT } from "../i18n";
import { Page, fmt } from "../ui";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";

type Sec = { totp_enabled: boolean; api_keys: { id: number; name: string; prefix: string; created_at: string; last_used_at: string | null }[] };
export default function Account() {
  const { t } = useT(); const { user } = useAuth();
  const [sec, setSec] = useState<Sec | null>(null); const [setup, setSetup] = useState<{ secret: string; otpauth: string } | null>(null);
  const [code, setCode] = useState(""); const [pw, setPw] = useState({ current: "", new: "" }); const [keyName, setKeyName] = useState(""); const [newKey, setNewKey] = useState<string | null>(null);
  const load = () => api.get("/me/security").then((r) => setSec(r.data));
  useEffect(() => { load(); }, []);
  const run = async (fn: () => Promise<any>, ok: string) => { try { await fn(); toast.success(ok); load(); } catch (x) { toast.error(errMsg(x)); } };
  if (!user) return null;
  return <Page title={t("My account")} icon={UserCircle} subtitle={t("Your profile, sign-in security and API keys.")}>
    <div className="grid gap-4 lg:grid-cols-2">
      <Card><CardHeader><div><CardTitle>{t("Profile")}</CardTitle><CardDescription>{t("How you appear to your colleagues.")}</CardDescription></div></CardHeader>
        <CardContent className="space-y-1 text-sm"><div className="font-medium">{user.full_name}</div><div className="text-muted-foreground">{user.email}</div><Badge className="mt-2 capitalize">{user.role.replace("_", " ")}</Badge></CardContent></Card>
      <Card><CardHeader><div><CardTitle>{t("Change password")}</CardTitle><CardDescription>{t("At least 8 characters.")}</CardDescription></div></CardHeader>
        <CardContent><form className="space-y-3" onSubmit={(e) => { e.preventDefault(); run(() => api.post("/me/password", pw), t("Password updated")).then(() => setPw({ current: "", new: "" })); }}>
          <div><Label htmlFor="pc">{t("Current password")}</Label><Input id="pc" type="password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} /></div>
          <div><Label htmlFor="pn">{t("New password")}</Label><Input id="pn" type="password" value={pw.new} onChange={(e) => setPw({ ...pw, new: e.target.value })} /></div>
          <Button size="sm" disabled={!pw.current || pw.new.length < 8}>{t("Update password")}</Button></form></CardContent></Card>
      <Card><CardHeader><div><CardTitle className="flex items-center gap-2"><ShieldCheck className="size-4 text-primary" />{t("Two-step sign-in")}</CardTitle><CardDescription>{t("Add a code from an authenticator app each time you sign in.")}</CardDescription></div>
        {sec && <Badge tone={sec.totp_enabled ? "green" : "neutral"}>{sec.totp_enabled ? t("On") : t("Off")}</Badge>}</CardHeader>
        <CardContent className="space-y-3 text-sm">
          {sec?.totp_enabled ? <>
            <p className="text-muted-foreground">{t("To turn it off, enter a current code from your app.")}</p>
            <div className="flex gap-2"><Input aria-label={t("Verification code")} placeholder="123456" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} className="w-32 font-mono" />
              <Button size="sm" variant="outline" disabled={code.length !== 6} onClick={() => run(() => api.post("/me/2fa/disable", { code }), t("Two-step sign-in is off")).then(() => setCode(""))}>{t("Turn off")}</Button></div></>
          : setup ? <>
            <div className="flex gap-4"><div className="rounded-lg border bg-white p-2"><QRCodeSVG value={setup.otpauth} size={132} /></div>
              <div className="space-y-2"><p>{t("1. Scan this with Google or Microsoft Authenticator.")}</p><p className="text-muted-foreground">{t("Can't scan? Enter this key:")}</p><code className="block break-all rounded bg-muted px-2 py-1 text-xs">{setup.secret}</code><p>{t("2. Enter the 6-digit code it shows.")}</p></div></div>
            <div className="flex gap-2"><Input aria-label={t("Verification code")} placeholder="123456" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} className="w-32 font-mono" />
              <Button size="sm" disabled={code.length !== 6} onClick={() => run(() => api.post("/me/2fa/enable", { code }), t("Two-step sign-in is on. Nice!")).then(() => { setCode(""); setSetup(null); })}>{t("Turn on")}</Button></div></>
          : <Button size="sm" onClick={async () => { try { setSetup((await api.post("/me/2fa/setup")).data); } catch (x) { toast.error(errMsg(x)); } }}>{t("Set up two-step sign-in")}</Button>}
        </CardContent></Card>
      {user.role !== "end_user" && <Card><CardHeader><div><CardTitle className="flex items-center gap-2"><KeyRound className="size-4 text-primary" />{t("API keys")}</CardTitle><CardDescription>{t("Let scripts and tools use Neurealm Service Desk as you. Send the key as a Bearer token.")}</CardDescription></div></CardHeader>
        <CardContent className="space-y-3 text-sm">
          {newKey && <div className="rounded-lg border border-primary/30 bg-accent p-3"><div className="font-medium">{t("Copy your key now. We won't show it again.")}</div>
            <div className="mt-2 flex items-center gap-2"><code className="flex-1 break-all rounded bg-card px-2 py-1 text-xs">{newKey}</code><Button size="sm" variant="outline" onClick={() => { navigator.clipboard?.writeText(newKey); toast.success(t("Copied")); }}><Copy /></Button></div></div>}
          <form className="flex gap-2" onSubmit={async (e) => { e.preventDefault(); try { const r = await api.post("/me/api-keys", { name: keyName }); setNewKey(r.data.key); setKeyName(""); load(); } catch (x) { toast.error(errMsg(x)); } }}>
            <Input aria-label={t("Key name")} placeholder={t("e.g. Monitoring script")} value={keyName} onChange={(e) => setKeyName(e.target.value)} /><Button size="sm" disabled={!keyName.trim()}>{t("Create key")}</Button></form>
          <div className="divide-y rounded-lg border">{(sec?.api_keys || []).length === 0 ? <div className="p-3 text-muted-foreground">{t("No keys yet.")}</div> : sec!.api_keys.map((k) =>
            <div key={k.id} className="flex items-center justify-between gap-2 p-3"><div><div className="font-medium">{k.name}</div><div className="text-xs text-muted-foreground"><code>{k.prefix}…</code> · {t("created")} {fmt(k.created_at)} · {k.last_used_at ? `${t("last used")} ${fmt(k.last_used_at)}` : t("never used")}</div></div>
              <Button size="sm" variant="ghost" aria-label={t("Revoke")} onClick={() => run(() => api.delete(`/me/api-keys/${k.id}`), t("Key revoked"))}><Trash2 className="text-red-500" /></Button></div>)}</div>
        </CardContent></Card>}
    </div>
  </Page>;
}
