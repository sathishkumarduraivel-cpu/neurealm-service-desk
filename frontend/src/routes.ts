import { lazy, type ComponentType, type LazyExoticComponent } from "react";
// Extra (module-specific) pages, code-split per page.
export const EXTRA_ROUTES: [string, LazyExoticComponent<ComponentType<any>>][] = [
  ["/cmdb", lazy(() => import("./pages/Cmdb"))],
  ["/events", lazy(() => import("./pages/Events"))],
  ["/itam", lazy(() => import("./pages/Itam"))],
  ["/costs", lazy(() => import("./pages/Costs"))],
  ["/csm", lazy(() => import("./pages/Csm").then((m) => ({ default: m.CsmOverview })))],
  ["/customer", lazy(() => import("./pages/Csm").then((m) => ({ default: m.CustomerPortal })))],
  ["/hr", lazy(() => import("./pages/Hr"))],
  ["/workplace", lazy(() => import("./pages/Workplace"))],
  ["/fsm", lazy(() => import("./pages/Fsm"))],
  ["/secops", lazy(() => import("./pages/SecOps"))],
  ["/grc", lazy(() => import("./pages/Grc"))],
  ["/spm", lazy(() => import("./pages/Spm"))],
  ["/autoresolve", lazy(() => import("./pages/Autonomy"))],
  ["/workflows", lazy(() => import("./pages/Workflows"))],
  ["/quality", lazy(() => import("./pages/Quality"))],
  ["/dex", lazy(() => import("./pages/Dex"))],
  ["/finops", lazy(() => import("./pages/FinOps"))],
  ["/patch", lazy(() => import("./pages/Patch"))],
  ["/integrations", lazy(() => import("./pages/Integrations"))],
];
