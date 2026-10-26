// Shared chart styling so every Recharts visual uses the same palette, axes and tooltip.
export const PALETTE = ["#1863DC", "#168AFF", "#10b981", "#f59e0b", "#081160", "#E5002B", "#14b8a6", "#64748b"];
export const PRIORITY_COLORS: Record<string, string> = { P1: "#ef4444", P2: "#f97316", P3: "#f59e0b", P4: "#94a3b8" };
export const axis = { tickLine: false, axisLine: false, tick: { fill: "hsl(var(--muted-foreground))", fontSize: 11 }, tickMargin: 8 } as const;
export const grid = { strokeDasharray: "3 3", stroke: "hsl(var(--border))", vertical: false } as const;
export function ChartTooltip({ active, payload, label, formatter }: any) {
  if (!active || !payload?.length) return null;
  return <div className="min-w-[140px] rounded-lg border bg-popover px-3 py-2 text-xs shadow-pop">
    {label != null && <div className="mb-1.5 font-medium text-foreground">{label}</div>}
    {payload.map((p: any) => <div key={p.dataKey + p.name} className="flex items-center gap-2 py-0.5"><span className="size-2 rounded-sm" style={{ background: p.color || p.payload?.fill }} /><span className="flex-1 capitalize text-muted-foreground">{p.name}</span><span className="font-medium tabular-nums text-foreground">{formatter ? formatter(p.value) : p.value}</span></div>)}
  </div>;
}
