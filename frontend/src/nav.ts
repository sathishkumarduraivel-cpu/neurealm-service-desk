import type { LucideIcon } from "lucide-react";
import { Activity, AlertOctagon, BadgeCheck, BarChart3, Bell, Bot, BookOpen, Briefcase, Bug, Building2, CalendarClock, CheckSquare, ClipboardList, Cloud, Contact,
  CalendarDays, Network, Sparkles, Server, Code2, BookMarked, Compass, LayoutDashboard, FileSignature, Siren, FolderKanban, Gauge, GitBranch, Handshake, Headphones, Home, IdCard, Inbox, KeyRound, Laptop, LayoutList, Lightbulb, Map, MonitorSmartphone, Plug, Puzzle, Radar, Receipt, RefreshCcw, Scale, Settings, ShieldAlert, ShoppingBag, SlidersHorizontal, Truck, Users, Wallet, Wrench } from "lucide-react";
export type NavItem = { to: string; label: string; icon: LucideIcon; roles?: string[]; feature?: string };
export type NavGroup = { id: string; label: string; items: NavItem[] };
const S = ["admin", "agent"], A = ["admin"];
const i = (to: string, label: string, icon: LucideIcon, roles?: string[], feature?: string): NavItem => ({ to, label, icon, roles, feature });
/** Optional modules an admin can switch on in Administration → Features. Off by default. */
export const FEATURES: { key: string; label: string; hint: string }[] = [
  { key: "events", label: "Event Management", hint: "Monitoring events and alert correlation" },
  { key: "fsm", label: "Field Service", hint: "Work orders for on-site technicians" },
  { key: "dex", label: "Digital Experience", hint: "Device health and experience scores" },
  { key: "patch", label: "Patch Management", hint: "Patch rings and rollouts" },
  { key: "costs", label: "Cloud & SaaS Usage", hint: "Cloud and SaaS usage tracking" },
  { key: "finops", label: "FinOps", hint: "Cloud optimisation recommendations" },
  { key: "csm", label: "Customer Service", hint: "Accounts, contacts, cases and entitlements" },
  { key: "workplace", label: "Workplace", hint: "Rooms, reservations and visitors" },
  { key: "spm", label: "Portfolio", hint: "Demands and projects" },
  { key: "secops", label: "Security Operations", hint: "Security incidents and vulnerabilities" },
  { key: "grc", label: "GRC & Compliance", hint: "Risks and controls" },
  { key: "autonomy", label: "Auto-Resolution", hint: "Let Neurealm AI resolve simple tickets" },
  { key: "quality", label: "Quality Reviews", hint: "Ticket quality audits" },
];
export const NAV: NavGroup[] = [
  { id: "home", label: "", items: [i("/dashboard", "Dashboard", Gauge, S), i("/help", "User guide", BookOpen), i("/analytics/boards", "Boards", LayoutDashboard, S), i("/analytics/explore", "Explore & pivot", Compass, S), i("/analytics/reports", "Report library", BookMarked, S), i("/reports/ask", "Ask for a report", Sparkles, S), i("/portal", "Self-Service", Home), i("/notifications", "Inbox", Bell)] },
  { id: "svc", label: "Service Desk", items: [i("/workbench", "Ticket Workbench", LayoutList, S), i("/incidents", "Incidents", AlertOctagon), i("/requests", "Service Requests", Inbox), i("/problems", "Problem Management", Puzzle, S),
    i("/changes", "Change Management", RefreshCcw, S), i("/change-ops", "Change Calendar & CAB", CalendarDays, S), i("/major-incidents", "Major Incidents", Siren, S), i("/approvals", "Approvals", CheckSquare, S), i("/catalog", "Service Catalog", ShoppingBag), i("/knowledge", "Knowledge Base", BookOpen)] },
  { id: "people", label: "People", items: [i("/hr", "Onboarding / Offboarding", Briefcase)] },
  { id: "assets", label: "Assets & Procurement", items: [i("/itam", "Assets Overview", BarChart3, S), i("/m/asset", "Assets", Laptop, S), i("/cmdb", "CMDB", Map, S), i("/cmdb/insights", "CMDB Insights", Network, S), i("/itam/compliance", "Licences & Contracts", KeyRound, S), i("/m/purchase_order", "Purchase Orders", Receipt, S), i("/m/license", "Licences", KeyRound, S), i("/m/contract", "Contracts", FileSignature, S)] },
  { id: "more", label: "More modules", items: [i("/events", "Event Management", Radar, S, "events"), i("/fsm", "Field Service", Truck, S, "fsm"), i("/dex", "Digital Experience", MonitorSmartphone, S, "dex"),
    i("/patch", "Patch Management", Wrench, S, "patch"), i("/costs", "Cloud & SaaS Usage", Cloud, S, "costs"), i("/finops", "FinOps", Wallet, S, "finops"),
    i("/csm", "Account 360", Handshake, S, "csm"), i("/m/case", "Cases", Headphones, S, "csm"), i("/m/account", "Accounts", Building2, S, "csm"), i("/m/contact", "Contacts", Contact, S, "csm"),
    i("/m/entitlement", "Entitlements", Receipt, S, "csm"), i("/customer", "Customer Portal", Users, undefined, "csm"), i("/workplace", "Workplace", Building2, undefined, "workplace"),
    i("/m/reservation", "Reservations", CalendarClock, undefined, "workplace"), i("/m/visitor", "Visitors", IdCard, S, "workplace"), i("/spm", "Portfolio", FolderKanban, S, "spm"),
    i("/m/demand", "Demands", Lightbulb, undefined, "spm"), i("/m/project", "Projects", ClipboardList, S, "spm"), i("/secops", "Security Operations", ShieldAlert, S, "secops"),
    i("/m/vulnerability", "Vulnerabilities", Bug, S, "secops"), i("/grc", "GRC & Compliance", Scale, S, "grc"), i("/m/risk", "Risks", Activity, S, "grc"), i("/m/control", "Controls", SlidersHorizontal, S, "grc"),
    i("/autoresolve", "Auto-Resolution", Bot, S, "autonomy"), i("/quality", "Quality Reviews", BadgeCheck, S, "quality")] },
  { id: "config", label: "Configuration", items: [i("/workflows", "Workflows & Automation", GitBranch, S), i("/integrations", "Integrations", Plug, S), i("/admin/forms", "Form designer", LayoutList, A), i("/admin/catalog", "Catalog builder", ShoppingBag, A), i("/admin/ai", "Neurealm AI", Sparkles, A), i("/admin/platform", "Email, alerts & data", Server, A), i("/developers", "Developer API", Code2, S), i("/admin/service-ops", "SLA & Assignment", Gauge, A), i("/admin/ticketing", "Ticket Settings", SlidersHorizontal, A), i("/admin", "Admin Settings", Settings, A)] },
];
export const ALL_ITEMS = NAV.flatMap((g) => g.items.map((it) => ({ ...it, group: g.label })));
export const titleFor = (path: string) => { const m = [...ALL_ITEMS].sort((a, b) => b.to.length - a.to.length).find((it) => path === it.to || path.startsWith(it.to + "/")); return m; };
export { S as STAFF, A as ADMIN };
export function addNav(..._a: unknown[]) {}
