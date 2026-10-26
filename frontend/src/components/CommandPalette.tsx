import { useEffect, useState } from "react";
import { Command } from "cmdk";
import { useNavigate } from "react-router-dom";
import { CornerDownLeft, FileText, Plus, Search, LogOut } from "lucide-react";
import * as DialogP from "@radix-ui/react-dialog";
import { ALL_ITEMS } from "@/nav";
import { api } from "@/api";
import { useAuth } from "@/auth";
import { pathFor } from "@/modules";
import { State, Priority } from "@/ui";
import { Kbd } from "@/components/ui/misc";

const Item = ({ onSelect, children, value }: { onSelect: () => void; children: React.ReactNode; value: string }) => (
  <Command.Item value={value} onSelect={onSelect} className="flex cursor-default items-center gap-2.5 rounded-md px-2.5 py-2 text-sm aria-selected:bg-accent [&_svg]:size-4 [&_svg]:text-muted-foreground">{children}</Command.Item>);
const Group = ({ heading, children }: { heading: string; children: React.ReactNode }) => (
  <Command.Group heading={heading} className="px-1.5 pb-1.5 [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground">{children}</Command.Group>);

export function CommandPalette({ open, setOpen }: { open: boolean; setOpen: (b: boolean) => void }) {
  const nav = useNavigate(); const { user, logout } = useAuth();
  const [q, setQ] = useState(""); const [hits, setHits] = useState<any[]>([]);
  useEffect(() => { const k = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen(!open); } }; window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k); }, [open]);
  useEffect(() => { if (q.trim().length < 2) { setHits([]); return; } const t = setTimeout(() => api.get("/search", { params: { q } }).then((r) => setHits(r.data)).catch(() => setHits([])), 180); return () => clearTimeout(t); }, [q]);
  const go = (to: string) => { setOpen(false); setQ(""); nav(to); };
  const items = ALL_ITEMS.filter((i) => !i.roles || (user && i.roles.includes(user.role)));
  return (
    <DialogP.Root open={open} onOpenChange={setOpen}>
      <DialogP.Portal>
        <DialogP.Overlay className="fixed inset-0 z-50 bg-slate-950/40 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <DialogP.Content className="fixed start-1/2 top-[12%] z-50 w-full max-w-xl -translate-x-1/2 overflow-hidden rounded-xl border bg-popover shadow-pop data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95">
          <DialogP.Title className="sr-only">Command palette</DialogP.Title>
          <Command shouldFilter={true} loop className="flex flex-col">
            <div className="flex items-center gap-2 border-b px-3.5"><Search className="size-4 text-muted-foreground" />
              <Command.Input value={q} onValueChange={setQ} autoFocus placeholder="Search records, pages and actions…" className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground" /><Kbd>ESC</Kbd></div>
            <Command.List className="max-h-[400px] overflow-y-auto py-1">
              <Command.Empty className="py-10 text-center text-sm text-muted-foreground">No results for “{q}”.</Command.Empty>
              {hits.length > 0 && <Group heading="Records">{hits.map((h) => <Item key={h.module + h.id} value={`${h.number} ${h.title} ${q}`} onSelect={() => go(`${pathFor(h.module)}/${h.id}`)}>
                <FileText /><span className="font-mono text-xs text-muted-foreground w-24 shrink-0">{h.number}</span><span className="flex-1 truncate">{h.title}</span>{h.priority && <Priority p={h.priority} />}<State s={h.state} /></Item>)}</Group>}
              <Group heading="Quick actions">
                <Item value="create new incident report issue" onSelect={() => go("/incidents/new")}><Plus />Report an incident</Item>
                <Item value="order request catalog" onSelect={() => go("/catalog")}><Plus />Order from service catalog</Item>
                <Item value="sign out logout" onSelect={() => { setOpen(false); logout(); }}><LogOut />Sign out</Item>
              </Group>
              <Group heading="Navigate">{items.map((it) => <Item key={it.to} value={`${it.label} ${it.group}`} onSelect={() => go(it.to)}><it.icon /><span className="flex-1">{it.label}</span><span className="text-xs text-muted-foreground">{it.group}</span></Item>)}</Group>
            </Command.List>
            <div className="flex items-center justify-between border-t px-3.5 py-2 text-[11px] text-muted-foreground"><span className="flex items-center gap-1.5"><CornerDownLeft className="size-3" />to select</span><span className="flex items-center gap-1"><Kbd>⌘</Kbd><Kbd>K</Kbd> to toggle</span></div>
          </Command>
        </DialogP.Content>
      </DialogP.Portal>
    </DialogP.Root>
  );
}
