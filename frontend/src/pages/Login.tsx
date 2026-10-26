import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { ArrowRight, Bot, Eye, EyeOff, Lock, Shield, Sparkles, Timer } from "lucide-react";
import { useAuth } from "../auth";
import { useT } from "../i18n";
import { errMsg } from "../api";
import { Logo } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { FieldError, Input, Label } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const DEMO = [["admin@neurealm.com", "Admin@123", "Admin"], ["agent@neurealm.com", "Agent@123", "Agent"], ["user@neurealm.com", "User@123", "Employee"]];
const schema = z.object({ email: z.string().trim().email("Enter a valid work email"), password: z.string().min(1, "Password is required") });
const FEATURES = [[Sparkles, "Neurealm AI triage", "Suggests a category, priority and team so nothing waits in a queue."], [Bot, "Helpful automation", "Common fixes can run on their own, always with a person in the loop."],
  [Timer, "Gentle SLA nudges", "We flag work that is running late before it becomes a problem."], [Shield, "A clear audit trail", "Every change is recorded, so you always know who did what."]] as const;

export default function Login() {
  const { t } = useT(); const { login, verifyMfa } = useAuth(); const nav = useNavigate(); const [show, setShow] = useState(false);
  const [mfa, setMfa] = useState<string | null>(null); const [code, setCode] = useState(""); const [busy, setBusy] = useState(false); const [canRegister, setCanRegister] = useState(false);
  useEffect(() => { api.get("/auth/config").then((r) => setCanRegister(!!r.data.registration)).catch(() => {}); }, []);
  const done = (u: any) => { toast.success(t("Welcome back, {name}", { name: u.full_name.split(" ")[0] })); nav(u.role === "end_user" ? "/portal" : "/dashboard"); };
  const submitCode = async (e: React.FormEvent) => { e.preventDefault(); if (!mfa) return; setBusy(true); try { done(await verifyMfa(mfa, code)); } catch (x) { toast.error(t("Sign-in failed"), { description: errMsg(x) }); } finally { setBusy(false); } };
  const { register, handleSubmit, setValue, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { email: "agent@neurealm.com", password: "Agent@123" } });
  const submit = async (v: z.infer<typeof schema>) => { try { const r = await login(v.email, v.password); if ("mfa_token" in r) { setMfa(r.mfa_token); setCode(""); return; } done(r.user); } catch (x) { toast.error(t("Sign-in failed"), { description: errMsg(x) }); } };
  return (
    <div className="grid min-h-screen bg-background lg:grid-cols-[1.05fr_1fr]">
      <div className="relative hidden overflow-hidden bg-nr-navy text-white lg:flex lg:flex-col">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_20%_10%,rgba(22,138,255,0.45),transparent_60%),radial-gradient(ellipse_60%_50%_at_90%_90%,rgba(229,0,43,0.30),transparent_60%)]" />
        <div className="absolute inset-0 opacity-[0.07] [background-image:linear-gradient(to_right,white_1px,transparent_1px),linear-gradient(to_bottom,white_1px,transparent_1px)] [background-size:40px_40px] [mask-image:radial-gradient(ellipse_at_center,black,transparent_75%)]" />
        <div className="relative flex flex-1 flex-col p-12">
          <Logo className="[&_.text-muted-foreground]:text-white/60 [&_.text-nr-navy]:text-white" />
          <div className="my-auto max-w-lg">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-white/80 backdrop-blur"><span className="size-1.5 rounded-full bg-emerald-400" />A friendly service desk by Neurealm</div>
            <h1 className="mt-6 text-[44px] font-display font-semibold leading-[1.1] tracking-tight">{t("Help your people,")}<br /><span className="bg-gradient-to-r from-nr-orange via-nr-coral to-white bg-clip-text text-transparent">{t("without the hassle.")}</span></h1>
            <p className="mt-4 text-base leading-relaxed text-white/65">{t("Neurealm Service Desk brings tickets, requests, assets and knowledge together in one calm place, so your team can spend more time helping.")}</p>
            <div className="mt-10 grid grid-cols-2 gap-x-6 gap-y-6">{FEATURES.map(([I, ti, d]) => <div key={ti}><div className="flex size-8 items-center justify-center rounded-lg border border-white/10 bg-white/5"><I className="size-4 text-nr-orange" /></div>
              <div className="mt-3 text-sm font-medium">{t(ti)}</div><div className="mt-1 text-xs leading-relaxed text-white/55">{t(d)}</div></div>)}</div>
          </div>
          <div className="flex items-center justify-between text-xs text-white/45"><span>© {new Date().getFullYear()} Neurealm. All rights reserved.</span><span className="flex items-center gap-1.5"><Lock className="size-3" />SSO · SAML · OIDC ready</span></div>
        </div>
      </div>
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-[380px]">
          <Logo className="mb-10 lg:hidden" />
          <h2 className="text-2xl font-semibold tracking-tight">{t("Sign in to Neurealm Service Desk")}</h2>
          <p className="mt-1.5 text-sm text-muted-foreground">{t("Welcome back. Use your work account to continue.")}</p>
          <Button variant="outline" className="mt-8 w-full" type="button" onClick={() => toast.info("Single sign-on", { description: "Configure Azure AD or Okta under Admin → SSO to enable this." })}>
            <svg viewBox="0 0 23 23" className="size-4"><path fill="#f35325" d="M1 1h10v10H1z" /><path fill="#81bc06" d="M12 1h10v10H12z" /><path fill="#05a6f0" d="M1 12h10v10H1z" /><path fill="#ffba08" d="M12 12h10v10H12z" /></svg>Continue with Microsoft</Button>
          <div className="my-6 flex items-center gap-3 text-xs text-muted-foreground"><div className="h-px flex-1 bg-border" />{t("or with email")}<div className="h-px flex-1 bg-border" /></div>
          {mfa ? <form onSubmit={submitCode} className="space-y-4" noValidate>
            <div className="rounded-lg border bg-accent/60 p-3 text-sm"><div className="font-medium text-foreground">{t("Two-step sign-in")}</div><div className="mt-0.5 text-muted-foreground">{t("Open your authenticator app and enter the 6-digit code for Neurealm Service Desk.")}</div></div>
            <div><Label htmlFor="code">{t("Verification code")}</Label><Input id="code" autoFocus inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} className="h-11 text-center font-mono text-lg tracking-[0.5em]" /></div>
            <Button className="h-10 w-full" disabled={busy || code.length !== 6}>{busy ? t("Checking…") : t("Verify and sign in")}</Button>
            <button type="button" className="w-full text-xs text-muted-foreground hover:text-foreground" onClick={() => setMfa(null)}>{t("Use a different account")}</button>
          </form> : <form onSubmit={handleSubmit(submit)} className="space-y-4" noValidate>
            <div><Label htmlFor="email">{t("Work email")}</Label><Input id="email" autoComplete="email" {...register("email")} className={cn("h-10", errors.email && "border-destructive")} /><FieldError msg={errors.email?.message} /></div>
            <div><div className="flex items-center justify-between"><Label htmlFor="pw">{t("Password")}</Label><button type="button" className="mb-1.5 text-xs font-medium text-primary hover:underline" onClick={() => toast.info("Contact your Neurealm Service Desk administrator to reset your password.")}>Forgot password?</button></div>
              <div className="relative"><Input id="pw" type={show ? "text" : "password"} autoComplete="current-password" {...register("password")} className={cn("h-10 pe-10", errors.password && "border-destructive")} />
                <button type="button" onClick={() => setShow(!show)} className="absolute end-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:text-foreground" aria-label="Toggle password">{show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button></div><FieldError msg={errors.password?.message} /></div>
            <Button className="h-10 w-full" disabled={isSubmitting}>{isSubmitting ? t("Signing in…") : <>{t("Sign in")}<ArrowRight /></>}</Button>
          </form>}
          {canRegister && !mfa && <p className="mt-4 text-center text-sm text-muted-foreground">{t("New here?")} <Link to="/register" className="font-medium text-primary hover:underline">{t("Create an account")}</Link></p>}
          <div className="mt-8 rounded-lg border bg-muted/40 p-3"><div className="text-xs font-medium">Demo workspace · Neurealm</div><div className="mt-2 grid grid-cols-3 gap-2">
            {DEMO.map(([e, p, l]) => <button type="button" key={e} className="rounded-md border bg-card px-2 py-1.5 text-xs font-medium shadow-xs transition-colors hover:border-primary/40 hover:text-primary" onClick={() => { setValue("email", e); setValue("password", p); }}>{l}</button>)}</div></div>
        </div>
      </div>
    </div>
  );
}
