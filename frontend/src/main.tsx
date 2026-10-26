import { BRAND } from "@/brand";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, HashRouter } from "react-router-dom";
// Hash routing when the host has no SPA rewrite configured (VITE_HASH_ROUTER=1)
const Router = import.meta.env.VITE_HASH_ROUTER === "1" ? HashRouter : BrowserRouter;
import "./index.css";
import App from "./App";
// Report browser errors to the admin error log (only when signed in; never blocks the app).
const reportErr = (message: string, stack?: string) => { try { const t = localStorage.getItem("nrsd_token"); if (t) fetch((import.meta.env.VITE_API_URL || "") + "/api/errors/client", { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${t}` }, body: JSON.stringify({ message, stack, path: location.pathname }) }); } catch { /* ignore */ } };
window.addEventListener("error", (e) => reportErr(e.message, e.error?.stack));
window.addEventListener("unhandledrejection", (e) => reportErr(String(e.reason?.message || e.reason), e.reason?.stack));
createRoot(document.getElementById("root")!).render(<StrictMode><Router><App /></Router></StrictMode>);

document.title = BRAND.product;
