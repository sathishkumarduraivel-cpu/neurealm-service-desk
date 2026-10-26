import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 700, rollupOptions: { output: { manualChunks(id) {
    if (!id.includes("node_modules")) return;
    if (/react-dom|react-router|scheduler|\/react\//.test(id)) return "react";
    if (id.includes("@radix-ui")) return "radix";
    if (id.includes("@tanstack")) return "table";
    if (id.includes("recharts") || id.includes("d3-")) return "charts";
    return "vendor";
  } } } },
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: { host: true, port: 5173, proxy: { "/api": process.env.VITE_API_PROXY || "http://localhost:8000" } },
  preview: { host: true, port: 4173, proxy: { "/api": process.env.VITE_API_PROXY || "http://localhost:8000" } },
});
