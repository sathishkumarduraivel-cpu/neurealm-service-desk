import { BRAND } from "@/brand";
import { Suspense, useEffect, useState, type ReactNode } from "react";
import { Link, Navigate, NavLink, useLocation, useNavigate } from "react-router-dom";
import * as Collapsible from "@radix-ui/react-collapsible";
import { Bell, ChevronDown, ChevronsLeft, ChevronsRight, HelpCircle, Languages, UserCircle, LogOut, Menu, Search, Settings, Sparkles, X } from "lucide-react";
import { useAuth } from "@/auth";
import { api } from "@/api";
import { NAV, titleFor } from "@/nav";
import { useT, LANGUAGES } from "@/i18n";
import { useFeatures } from "@/features";
import { cn, relTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Avatar, Kbd, Skeleton, Tip } from "@/components/ui/misc";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger, DropdownMenuSub, DropdownMenuSubTrigger, DropdownMenuSubContent, Popover, PopoverContent, PopoverTrigger } from "@/components/ui/menu";
import { CommandPalette } from "./CommandPalette";
import { AssistantWidget } from "./NeurealmAI";

export const Logo = ({ compact, className }: { compact?: boolean; className?: string }) => (
  <div className={cn("flex items-center gap-2.5", className)}>
    <div className="relative flex size-7 shrink-0 items-center justify-center rounded-lg bg-nr-purple shadow-sm">
      <svg viewBox="0 0 24 24" className="size-4 text-white" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M6 18V6l12 12V6" /></svg>
    </div>
    {!compact && <div className="leading-none"><div className="font-display text-[15px] font-semibold tracking-tight text-nr-navy">{BRAND.product}</div><div className="mt-0.5 text-[10px] font-medium text-muted-foreground">by {BRAND.company}</div></div>}
  </div>
);

function useTenant() { const [t, setT] = useState<string>(""); useEffect(() => { api.get("/tenant").then((r) => setT(r.data.name)).catch(() => {}); }, []); return t; }

function Notifications() {
  const [items, setItems] = useState<any[] | null>(null); const [n, setN] = useState(0); const nav = useNavigate();
  const f = () => api.get("/notifications", { params: { unread: true } }).then((r) => { setN(r.data.length); setItems(r.data.slice(0, 6)); }).catch(() => {});
  useEffect(() => { f(); const t = setInterval(f, 30000); return () => clearInterval(t); }, []);
  return (
    <Popover><PopoverTrigger asChild><Button variant="ghost" size="icon-sm" className="relative" aria-label="Notifications"><Bell />{n > 0 && <span className="absolute end-1 top-1 flex size-3.5 items-center justify-center rounded-full bg-red-500 text-[9px] font-semibold text-white ring-2 ring-background">{n > 9 ? "9+" : n}</span>}</Button></PopoverTrigger>
      <PopoverContent className="w-96 p-0">
        <div className="flex items-center justify-between border-b px-4 py-2.5"><div className="text-sm font-semibold">Notifications</div><span className="text-xs text-muted-foreground">{n} unread</span></div>
        <div className="max-h-96 overflow-y-auto">{items === null ? <div className="space-y-2 p-4">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-10" />)}</div> : items.length === 0 ? <div className="p-8 text-center text-sm text-muted-foreground">You're all caught up.</div> :
          items.map((x) => <button key={x.id} onClick={() => x.link && nav(x.link)} className="flex w-full gap-3 border-b px-4 py-3 text-start last:border-0 hover:bg-accent/60">
            <span className={cn("mt-1.5 size-2 shrink-0 rounded-full", x.kind === "sla_breach" ? "bg-red-500" : x.kind === "sla_warning" || x.kind === "escalation" ? "bg-amber-500" : x.kind === "ai" ? "bg-violet-500" : "bg-indigo-500")} />
            <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{x.title}</span><span className="text-xs capitalize text-muted-foreground">{(x.kind || "info").replace(/_/g, " ")}</span><span className="mt-0.5 block text-[11px] text-muted-foreground/80">{relTime(x.created_at)}</span></span></button>)}</div>
        <Link to="/notifications" className="block border-t px-4 py-2 text-center text-xs font-medium text-primary hover:bg-accent/50">View all notifications</Link>
      </PopoverContent></Popover>
  );
}

function AiFooter() {
  const { t } = useT(); const [s, setS] = useState<{ llm_enabled: boolean } | null>(null);
  useEffect(() => { api.get("/ai/status").then((r) => setS(r.data)).catch(() => {}); }, []);
  return <div className="border-t border-sidebar-border p-3"><div className="rounded-lg border border-brand-100 bg-brand-50/60 p-3">
    <div className="flex items-center gap-1.5 text-xs font-semibold text-primary"><Sparkles className="size-3.5" />{t("Neurealm AI")}</div>
    <div className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{s?.llm_enabled ? "Here to help with triage and answers." : t("Neurealm AI is using smart rules until an AI key is added.")}</div></div></div>;
}

function Sidebar({ collapsed, setCollapsed, mobile, onNavigate }: { collapsed: boolean; setCollapsed?: (b: boolean) => void; mobile?: boolean; onNavigate?: () => void }) {
  const { user } = useAuth(); const loc = useLocation(); const { t } = useT(); const { enabled } = useFeatures();
  const [closed, setClosed] = useState<Record<string, boolean>>(() => JSON.parse(localStorage.getItem("nrsd_nav") || "{}"));
  useEffect(() => localStorage.setItem("nrsd_nav", JSON.stringify(closed)), [closed]);
  const vis = (r?: string[]) => !r || (!!user && r.includes(user.role));
  return (
    <aside className={cn("flex h-full flex-col border-e bg-sidebar text-sidebar-foreground transition-[width] duration-200", collapsed ? "w-[60px]" : "w-[248px]")}>
      <div className={cn("flex h-14 items-center border-b border-sidebar-border", collapsed ? "justify-center px-0" : "justify-between px-4")}>
        <Link to="/" className="text-foreground"><Logo compact={collapsed} /></Link>
        {!collapsed && !mobile && <Tip content="Collapse sidebar"><Button variant="ghost" size="icon-sm" className="text-muted-foreground" aria-label={t("Collapse sidebar")} onClick={() => setCollapsed?.(true)}><ChevronsLeft /></Button></Tip>}
      </div>
      <nav className="flex-1 overflow-y-auto px-2.5 py-3">
        {NAV.map((g) => { const items = g.items.filter((i) => vis(i.roles) && enabled(i.feature)); if (!items.length) return null; const active = items.some((i) => loc.pathname === i.to || loc.pathname.startsWith(i.to + "/"));
          const open = collapsed || !g.label || active || !closed[g.id];
          return (
            <Collapsible.Root key={g.id} open={open} onOpenChange={(o) => setClosed({ ...closed, [g.id]: !o })} className={cn(g.label && "mt-3")}>
              {g.label && !collapsed && <Collapsible.Trigger className="group flex w-full items-center justify-between rounded px-2 py-1 text-[11px] font-medium uppercase tracking-wider text-slate-600 hover:text-foreground">
                {t(g.label)}<ChevronDown className="size-3 transition-transform group-data-[state=closed]:-rotate-90" /></Collapsible.Trigger>}
              {g.label && collapsed && <div className="mx-auto my-2 h-px w-6 bg-sidebar-border" />}
              <Collapsible.Content className="mt-0.5 space-y-px">
                {items.map((it) => {
                  const link = <NavLink to={it.to} onClick={onNavigate} className={({ isActive }) => cn("group flex h-8 items-center gap-2.5 rounded-md px-2 text-[13px] font-medium transition-colors",
                    collapsed && "justify-center px-0", isActive ? "bg-sidebar-accent text-primary font-semibold" : "text-sidebar-foreground hover:bg-sidebar-accent/70 hover:text-foreground")}>
                    {({ isActive }) => <><it.icon className={cn("size-4 shrink-0", isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground")} />{!collapsed && <span className="truncate">{t(it.label)}</span>}</>}</NavLink>;
                  return collapsed ? <Tip key={it.to} content={t(it.label)}>{link}</Tip> : <div key={it.to}>{link}</div>;
                })}
              </Collapsible.Content>
            </Collapsible.Root>);
        })}
      </nav>
      {collapsed && !mobile && <div className="border-t border-sidebar-border p-2"><Tip content="Expand sidebar"><Button variant="ghost" size="icon-sm" className="mx-auto flex text-muted-foreground" aria-label={t("Expand sidebar")} onClick={() => setCollapsed?.(false)}><ChevronsRight /></Button></Tip></div>}
      {!collapsed && <AiFooter />}
    </aside>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout, impersonating, stopImpersonating } = useAuth(); const { t, lang, setLang } = useT(); const loc = useLocation(); const nav = useNavigate(); const tenant = useTenant();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("nrsd_collapsed") === "1"); const [cmd, setCmd] = useState(false); const [mob, setMob] = useState(false);
  useEffect(() => localStorage.setItem("nrsd_collapsed", collapsed ? "1" : "0"), [collapsed]);
  useEffect(() => setMob(false), [loc.pathname]);
  if (!user) return <Navigate to="/login" />;
  const cur = titleFor(loc.pathname);
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:start-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground">{t("Skip to main content")}</a>
      <div className="hidden lg:block"><Sidebar collapsed={collapsed} setCollapsed={setCollapsed} /></div>
      {mob && <div className="fixed inset-0 z-40 lg:hidden"><div className="absolute inset-0 bg-slate-950/40" onClick={() => setMob(false)} /><div className="absolute inset-y-0 start-0 shadow-pop"><Sidebar collapsed={false} mobile onNavigate={() => setMob(false)} /></div>
        <Button variant="secondary" size="icon-sm" className="absolute start-[256px] top-3" aria-label="Close menu" onClick={() => setMob(false)}><X /></Button></div>}
      <div className="flex min-w-0 flex-1 flex-col">
        {impersonating && <div role="status" className="flex items-center justify-center gap-3 bg-nr-orange px-4 py-1.5 text-sm font-medium text-white">
          <span>{t("You are viewing Neurealm Service Desk as {name}.", { name: user.full_name })}</span>
          <button className="rounded-md bg-white/20 px-2 py-0.5 text-xs font-semibold hover:bg-white/30" onClick={async () => { await stopImpersonating(); nav("/admin"); }}>{t("Switch back")}</button></div>}
        <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/70 lg:px-6">
          <Button variant="ghost" size="icon-sm" className="lg:hidden" onClick={() => setMob(true)}><Menu /></Button>
          <div className="hidden min-w-0 items-center gap-1.5 text-sm md:flex">
            {tenant && <><span className="inline-flex items-center gap-1.5 rounded-md border bg-card px-2 py-1 text-xs font-medium shadow-xs"><span className="size-1.5 rounded-full bg-emerald-500" />{tenant}</span><span className="text-muted-foreground/50">/</span></>}
            {cur && <span className="text-muted-foreground">{t(cur.group || "Home")}</span>}{cur && <><span className="text-muted-foreground/50">/</span><span className="truncate font-medium">{t(cur.label)}</span></>}
          </div>
          <div className="flex-1" />
          <button onClick={() => setCmd(true)} className="flex h-8 w-full max-w-[320px] items-center gap-2 rounded-md border bg-card px-2.5 text-sm text-muted-foreground shadow-xs transition-colors hover:bg-accent/60">
            <Search className="size-4" /><span className="flex-1 text-start">{t("Search Neurealm Service Desk…")}</span><Kbd>⌘K</Kbd></button>
          <Notifications />
          <DropdownMenu><DropdownMenuTrigger className="flex items-center gap-2 rounded-md p-1 outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"><Avatar name={user.full_name} size={26} /></DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-60">
              <div className="flex items-center gap-2.5 px-2 py-2"><Avatar name={user.full_name} size={32} /><div className="min-w-0"><div className="truncate text-sm font-medium">{user.full_name}</div><div className="truncate text-xs text-muted-foreground">{user.email}</div></div></div>
              <DropdownMenuSeparator /><DropdownMenuLabel className="flex justify-between">Role<span className="font-normal capitalize text-foreground">{user.role.replace("_", " ")}</span></DropdownMenuLabel>
              {tenant && <DropdownMenuLabel className="flex justify-between pt-0">Workspace<span className="font-normal text-foreground">{tenant}</span></DropdownMenuLabel>}
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => nav("/account")}><UserCircle />{t("My account")}</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => nav("/notifications")}><Bell />{t("Notifications")}</DropdownMenuItem>
              <DropdownMenuSub><DropdownMenuSubTrigger><Languages />{t("Language")}</DropdownMenuSubTrigger><DropdownMenuSubContent>
                {LANGUAGES.map((l) => <DropdownMenuItem key={l.code} onSelect={() => setLang(l.code)}>{l.name}{lang === l.code && <span className="ms-auto text-primary">✓</span>}</DropdownMenuItem>)}
              </DropdownMenuSubContent></DropdownMenuSub>
              {user.role === "admin" && <DropdownMenuItem onSelect={() => nav("/admin")}><Settings />{t("Admin Settings")}</DropdownMenuItem>}
              <DropdownMenuItem onSelect={() => nav("/knowledge")}><HelpCircle />{t("Help & knowledge")}</DropdownMenuItem>
              <DropdownMenuSeparator /><DropdownMenuItem onSelect={logout} className="text-red-600 focus:text-red-600 [&_svg]:text-red-500"><LogOut />{t("Sign out")}</DropdownMenuItem>
            </DropdownMenuContent></DropdownMenu>
        </header>
        <main id="main" tabIndex={-1} className="flex-1 overflow-y-auto focus:outline-none"><Suspense fallback={<PageSkeleton />}>{children}</Suspense></main>
        <AssistantWidget />
      </div>
      <CommandPalette open={cmd} setOpen={setCmd} />
    </div>
  );
}
export const PageSkeleton = () => <div className="mx-auto max-w-[1440px] space-y-5 px-6 py-6"><Skeleton className="h-8 w-64" /><div className="grid grid-cols-4 gap-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}</div><Skeleton className="h-72" /></div>;
