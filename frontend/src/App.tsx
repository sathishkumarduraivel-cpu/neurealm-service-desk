import UserGuide from "@/pages/UserGuide";
import ServiceOps from "./pages/ServiceOps";
import FormDesigner from "./pages/FormDesigner";
import CatalogAdmin from "./pages/CatalogAdmin";
import ChangeOps, { MajorIncidents } from "./pages/ChangeOps";
import CmdbTools, { ItamCompliance } from "./pages/CmdbTools";
import { AiReports, AiSettings } from "./pages/AiStudio";
import { BoardView, Boards, Explore, ReportLibrary } from "./pages/Analytics";
import Platform, { Developers } from "./pages/Platform";
import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { Toaster } from "sonner";
import { AppShell } from "./components/AppShell";
import { ThemeProvider, useTheme } from "./lib/theme";
import { TooltipProvider } from "./components/ui/misc";
import { AuthProvider, useAuth, isStaff } from "./auth";
import { ModulesProvider } from "./modules";
import { I18nProvider } from "./i18n";
import { FeaturesProvider } from "./features";

const Login = lazy(() => import("./pages/Login"));
const Register = lazy(() => import("./pages/Register"));
const Account = lazy(() => import("./pages/Account"));
const Workbench = lazy(() => import("./pages/Workbench"));
const TicketSettings = lazy(() => import("./pages/TicketSettings"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Records = lazy(() => import("./pages/Records").then((m) => ({ default: m.RecordList })));
const RecDetail = lazy(() => import("./pages/Records").then((m) => ({ default: m.RecordDetail })));
const RecCreate = lazy(() => import("./pages/Records").then((m) => ({ default: m.IncidentCreate })));
const Catalog = lazy(() => import("./pages/Catalog"));
const Knowledge = lazy(() => import("./pages/Knowledge").then((m) => ({ default: m.Knowledge })));
const KnowledgeArticle = lazy(() => import("./pages/Knowledge").then((m) => ({ default: m.KnowledgeArticle })));
const Portal = lazy(() => import("./pages/Portal"));
const Admin = lazy(() => import("./pages/Admin"));
const Approvals = lazy(() => import("./pages/Approvals"));
const Notifications = lazy(() => import("./pages/Notifications"));
import { EXTRA_ROUTES } from "./routes";

const S = (el: ReactNode) => <AppShell>{el}</AppShell>;
function Toasts() { const { theme } = useTheme(); return <Toaster theme={theme as "light"} position="bottom-right" richColors closeButton toastOptions={{ className: "font-sans" }} />; }
function Home() { const { user } = useAuth(); return <Navigate to={!user ? "/login" : isStaff(user) ? "/dashboard" : "/portal"} />; }
function M({ kind }: { kind: "list" | "new" | "detail" }) {
  const { module = "" } = useParams();
  return kind === "list" ? <Records key={module} module={module} /> : kind === "new" ? <RecCreate key={module} module={module} /> : <RecDetail key={module} module={module} />;
}

export default function App() {
  return (
    <ThemeProvider><I18nProvider><TooltipProvider><AuthProvider><FeaturesProvider><ModulesProvider><Toasts />
      <Suspense fallback={null}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/account" element={S(<Account />)} />
        <Route path="/workbench" element={S(<Workbench />)} />
        <Route path="/admin/service-ops" element={S(<ServiceOps />)} />
        <Route path="/admin/forms" element={S(<FormDesigner />)} />
        <Route path="/admin/catalog" element={S(<CatalogAdmin />)} />
        <Route path="/change-ops" element={S(<ChangeOps />)} />
        <Route path="/cmdb/insights" element={S(<CmdbTools />)} />
        <Route path="/reports/ask" element={S(<AiReports />)} />
        <Route path="/analytics/explore" element={S(<Explore />)} />
        <Route path="/admin/platform" element={S(<Platform />)} />
        <Route path="/help" element={S(<UserGuide />)} />
        <Route path="/developers" element={S(<Developers />)} />
        <Route path="/analytics/reports" element={S(<ReportLibrary />)} />
        <Route path="/analytics/boards" element={S(<Boards />)} />
        <Route path="/analytics/boards/:id" element={S(<BoardView />)} />
        <Route path="/admin/ai" element={S(<AiSettings />)} />
        <Route path="/itam/compliance" element={S(<ItamCompliance />)} />
        <Route path="/major-incidents" element={S(<MajorIncidents />)} />
        <Route path="/admin/ticketing" element={S(<TicketSettings />)} />
        <Route path="/" element={<Home />} />
        <Route path="/dashboard" element={S(<Dashboard />)} />
        {["incident", "problem", "change", "request"].map((m) => [
          <Route key={m} path={`/${m}s`} element={S(<Records module={m} />)} />,
          <Route key={m + "n"} path={`/${m}s/new`} element={S(<RecCreate module={m} />)} />,
          <Route key={m + "d"} path={`/${m}s/:id`} element={S(<RecDetail module={m} />)} />])}
        <Route path="/m/:module" element={S(<M kind="list" />)} />
        <Route path="/m/:module/new" element={S(<M kind="new" />)} />
        <Route path="/m/:module/:id" element={S(<M kind="detail" />)} />
        <Route path="/approvals" element={S(<Approvals />)} />
        <Route path="/catalog" element={S(<Catalog />)} />
        <Route path="/knowledge" element={S(<Knowledge />)} />
        <Route path="/knowledge/:id" element={S(<KnowledgeArticle />)} />
        <Route path="/portal" element={S(<Portal />)} />
        <Route path="/admin" element={S(<Admin />)} />
        <Route path="/notifications" element={S(<Notifications />)} />
        {EXTRA_ROUTES.map(([p, El]) => <Route key={p} path={p} element={S(<El />)} />)}
        <Route path="*" element={<Home />} />
      </Routes>
      </Suspense>
    </ModulesProvider></FeaturesProvider></AuthProvider></TooltipProvider></I18nProvider></ThemeProvider>
  );
}
