import { useMemo, useState, type ReactNode } from "react";
import { flexRender, getCoreRowModel, getFilteredRowModel, getPaginationRowModel, getSortedRowModel, useReactTable,
  type ColumnDef, type SortingState, type VisibilityState } from "@tanstack/react-table";
import { useT } from "@/i18n";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, ChevronsUpDown, Columns3, Inbox, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/input";
import { DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/menu";
import { EmptyState, Skeleton } from "@/components/ui/misc";
import { cn, humanize } from "@/lib/utils";

export type Facet = { id: string; label: string; options?: string[] };
export function DataTable<T>({ data, columns, loading, onRowClick, facets = [], toolbar, searchPlaceholder = "Filter…", empty, pageSize = 15, initialSort, onSearchSubmit, dense }: {
  data: T[]; columns: ColumnDef<T, any>[]; loading?: boolean; onRowClick?: (r: T) => void; facets?: Facet[]; toolbar?: ReactNode; searchPlaceholder?: string;
  empty?: ReactNode; pageSize?: number; initialSort?: SortingState; onSearchSubmit?: (q: string) => void; dense?: boolean }) {
  const [sorting, setSorting] = useState<SortingState>(initialSort || []); const [global, setGlobal] = useState(""); const [vis, setVis] = useState<VisibilityState>({});
  const { t } = useT();
  const [filters, setFilters] = useState<Record<string, string>>({});
  const filtered = useMemo(() => data.filter((r: any) => Object.entries(filters).every(([k, v]) => !v || String(r[k] ?? "") === v)), [data, filters]);
  const table = useReactTable({ data: filtered, columns, state: { sorting, globalFilter: global, columnVisibility: vis }, onSortingChange: setSorting, onGlobalFilterChange: setGlobal, onColumnVisibilityChange: setVis,
    getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), getFilteredRowModel: getFilteredRowModel(), getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } }, globalFilterFn: (row, _c, v) => JSON.stringify(row.original).toLowerCase().includes(String(v).toLowerCase()) });
  const facetOpts = (f: Facet) => f.options || [...new Set(data.map((r: any) => r[f.id]).filter((x) => x != null && x !== ""))].sort();
  const active = Object.values(filters).some(Boolean) || !!global;
  const { pageIndex, pageSize: ps } = table.getState().pagination; const total = table.getFilteredRowModel().rows.length;
  return (
    <div className="rounded-lg border bg-card shadow-xs">
      <div className="flex flex-wrap items-center gap-2 border-b p-3">
        <div className="relative w-full max-w-xs"><Search className="pointer-events-none absolute start-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input className="input h-8 ps-8" placeholder={t(searchPlaceholder)} value={global} onChange={(e) => setGlobal(e.target.value)} onKeyDown={(e) => e.key === "Enter" && onSearchSubmit?.(global)} /></div>
        {facets.map((f) => <NativeSelect key={f.id} aria-label={`${t("Filter by")} ${t(f.label ?? f.id)}`} className={cn("h-8 w-auto min-w-[130px] text-xs capitalize", filters[f.id] && "border-primary/50 bg-primary/5 text-primary")} value={filters[f.id] || ""} onChange={(e) => setFilters({ ...filters, [f.id]: e.target.value })}>
          <option value="">{t(f.label)}: {t("All")}</option>{facetOpts(f).map((o) => <option key={o} value={o}>{t(humanize(o))}</option>)}</NativeSelect>)}
        {active && <Button variant="ghost" size="sm" onClick={() => { setFilters({}); setGlobal(""); }}><X />Reset</Button>}
        <div className="flex-1" />{toolbar}
        <DropdownMenu><DropdownMenuTrigger asChild><Button variant="outline" size="sm"><Columns3 />{t("View")}</Button></DropdownMenuTrigger>
          <DropdownMenuContent align="end"><DropdownMenuLabel>Toggle columns</DropdownMenuLabel><DropdownMenuSeparator />
            {table.getAllLeafColumns().filter((c) => c.getCanHide()).map((c) => <DropdownMenuCheckboxItem key={c.id} checked={c.getIsVisible()} onCheckedChange={(v) => c.toggleVisibility(!!v)} onSelect={(e) => e.preventDefault()}>{String(c.columnDef.header ?? c.id)}</DropdownMenuCheckboxItem>)}</DropdownMenuContent></DropdownMenu>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full caption-bottom text-sm">
          <thead>{table.getHeaderGroups().map((hg) => <tr key={hg.id}>{hg.headers.map((h) => { const s = h.column.getIsSorted(); const can = h.column.getCanSort();
            return <th key={h.id} className="h-9 border-b bg-muted/40 px-3 text-start align-middle text-xs font-medium text-muted-foreground whitespace-nowrap" style={{ width: h.column.columnDef.size !== 150 ? h.column.columnDef.size : undefined }}>
              {can ? <button className="-ms-1.5 inline-flex items-center gap-1 rounded px-1.5 py-1 hover:bg-accent hover:text-foreground" onClick={h.column.getToggleSortingHandler()}>{(typeof h.column.columnDef.header === "string" ? t(h.column.columnDef.header) : flexRender(h.column.columnDef.header, h.getContext()))}
                {s === "asc" ? <ArrowUp className="size-3" /> : s === "desc" ? <ArrowDown className="size-3" /> : <ChevronsUpDown className="size-3 opacity-40" />}</button> : (typeof h.column.columnDef.header === "string" ? t(h.column.columnDef.header) : flexRender(h.column.columnDef.header, h.getContext()))}</th>; })}</tr>)}</thead>
          <tbody>
            {loading ? [...Array(8)].map((_, i) => <tr key={i}>{table.getVisibleLeafColumns().map((c, j) => <td key={c.id} className="border-b px-4 py-3"><Skeleton className={cn("h-4", j === 1 ? "w-56" : "w-16")} /></td>)}</tr>)
              : table.getRowModel().rows.map((row) => <tr key={row.id} onClick={() => onRowClick?.(row.original)} className={cn("border-b transition-colors last:border-0 hover:bg-muted/40", onRowClick && "cursor-pointer")}>
                {row.getVisibleCells().map((cell) => <td key={cell.id} className={cn("px-3 align-middle", dense ? "py-2" : "py-2.5")}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}</tr>)}
          </tbody>
        </table>
        {!loading && total === 0 && (empty || <EmptyState icon={Inbox} title={active ? "No matching records" : "No records yet"} desc={active ? "Try adjusting your search or filters." : "Records you create will appear here."} />)}
      </div>
      {total > 0 && <div className="flex items-center justify-between gap-3 border-t px-4 py-2.5 text-xs text-muted-foreground">
        <span>Showing <b className="font-medium text-foreground tabular-nums">{pageIndex * ps + 1}–{Math.min(total, (pageIndex + 1) * ps)}</b> of <b className="font-medium text-foreground tabular-nums">{total}</b></span>
        <div className="flex items-center gap-2"><span className="flex items-center gap-1.5">{t("Rows")}<NativeSelect aria-label={t("Rows per page")} className="h-7 w-[68px] text-xs" value={ps} onChange={(e) => table.setPageSize(+e.target.value)}>{[10, 15, 25, 50, 100].map((n) => <option key={n}>{n}</option>)}</NativeSelect></span>
          <span className="tabular-nums">{t("Page {n} of {m}", { n: pageIndex + 1, m: Math.max(1, table.getPageCount()) })}</span>
          <Button variant="outline" size="icon-sm" className="size-7" aria-label={t("Previous page")} disabled={!table.getCanPreviousPage()} onClick={() => table.previousPage()}><ChevronLeft /></Button>
          <Button variant="outline" size="icon-sm" className="size-7" aria-label={t("Next page")} disabled={!table.getCanNextPage()} onClick={() => table.nextPage()}><ChevronRight /></Button></div>
      </div>}
    </div>
  );
}
