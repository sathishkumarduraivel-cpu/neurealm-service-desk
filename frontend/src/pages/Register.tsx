import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { UserPlus } from "lucide-react";
import { useAuth } from "../auth";
import { api, errMsg } from "../api";
import { useT } from "../i18n";
import { Logo } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";

export default function Register() {
  const { t } = useT(); const { register } = useAuth(); const nav = useNavigate();
  const [cfg, setCfg] = useState<{ registration: boolean; domain: string | null } | null>(null);
  const [f, setF] = useState({ full_name: "", email: "", password: "" }); const [busy, setBusy] = useState(false);
  useEffect(() => { api.get("/auth/config").then((r) => setCfg(r.data)).catch(() => setCfg({ registration: false, domain: null })); }, []);
  const submit = async (e: React.FormEvent) => { e.preventDefault(); setBusy(true);
    try { const u = await register(f.full_name, f.email, f.password); toast.success(t("Welcome to Neurealm Service Desk, {name}!", { name: u.full_name.split(" ")[0] })); nav("/portal"); }
    catch (x) { toast.error(t("We couldn't create your account"), { description: errMsg(x) }); } finally { setBusy(false); } };
  return <div className="flex min-h-screen items-center justify-center bg-background p-6">
    <div className="w-full max-w-[400px] rounded-xl border bg-card p-8 shadow-sm">
      <Logo className="mb-8" />
      <h2 className="text-2xl font-semibold tracking-tight">{t("Create your account")}</h2>
      {cfg && !cfg.registration ? <p className="mt-3 text-sm text-muted-foreground">{t("Self sign-up is turned off. Please ask your administrator for an invite.")}</p> :
      <><p className="mt-1.5 text-sm text-muted-foreground">{cfg?.domain ? t("Use your @{domain} work email to get started.", { domain: cfg.domain }) : t("Use your work email to get started.")}</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <div><Label htmlFor="rn">{t("Full name")}</Label><Input id="rn" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} className="h-10" /></div>
        <div><Label htmlFor="re">{t("Work email")}</Label><Input id="re" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} className="h-10" /></div>
        <div><Label htmlFor="rp">{t("Password")}</Label><Input id="rp" type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} className="h-10" /><p className="mt-1 text-xs text-muted-foreground">{t("At least 8 characters.")}</p></div>
        <Button className="h-10 w-full" disabled={busy}><UserPlus />{busy ? t("Creating…") : t("Create account")}</Button>
      </form></>}
      <p className="mt-6 text-center text-sm text-muted-foreground">{t("Already have an account?")} <Link to="/login" className="font-medium text-primary hover:underline">{t("Sign in")}</Link></p>
    </div>
  </div>;
}
