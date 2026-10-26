import { useT } from "@/i18n";
import * as React from "react";
import * as AvatarP from "@radix-ui/react-avatar";
import * as TooltipP from "@radix-ui/react-tooltip";
import * as TabsP from "@radix-ui/react-tabs";
import * as SwitchP from "@radix-ui/react-switch";
import * as ProgressP from "@radix-ui/react-progress";
import * as SepP from "@radix-ui/react-separator";
import { cn, initials, avatarColor } from "@/lib/utils";

export const Skeleton = ({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) => <div className={cn("animate-pulse rounded-md bg-muted", className)} {...p} />;
export const Separator = ({ className, orientation = "horizontal" }: { className?: string; orientation?: "horizontal" | "vertical" }) =>
  <SepP.Root orientation={orientation} className={cn("shrink-0 bg-border", orientation === "horizontal" ? "h-px w-full" : "h-full w-px", className)} />;

export function Avatar({ name, size = 24, className }: { name?: string | null; size?: number; className?: string }) {
  return <AvatarP.Root className={cn("inline-flex shrink-0 select-none items-center justify-center overflow-hidden rounded-full text-white font-semibold", avatarColor(name), className)} style={{ width: size, height: size, fontSize: Math.max(9, size * 0.38) }} title={name || ""}>
    <AvatarP.Fallback>{initials(name)}</AvatarP.Fallback></AvatarP.Root>;
}
const UnassignedLabel = () => { const { t } = useT(); return <span className="text-muted-foreground">{t("Unassigned")}</span>; };
export const Person = ({ name, sub }: { name?: string | null; sub?: string }) => !name ? <UnassignedLabel /> :
  <span className="inline-flex items-center gap-2 min-w-0"><Avatar name={name} size={22} /><span className="truncate">{name}{sub && <span className="block text-xs text-muted-foreground">{sub}</span>}</span></span>;

export const TooltipProvider = TooltipP.Provider;
export function Tip({ content, children, side = "right" }: { content: React.ReactNode; children: React.ReactNode; side?: "top" | "right" | "bottom" | "left" }) {
  return <TooltipP.Root delayDuration={200}><TooltipP.Trigger asChild>{children}</TooltipP.Trigger>
    <TooltipP.Portal><TooltipP.Content side={side} sideOffset={6} className="z-50 rounded-md bg-slate-900 px-2 py-1 text-xs text-white shadow-pop animate-in fade-in-0 zoom-in-95">{content}</TooltipP.Content></TooltipP.Portal></TooltipP.Root>;
}

export const Tabs = TabsP.Root;
export const TabsList = ({ className, ...p }: React.ComponentProps<typeof TabsP.List>) => <TabsP.List className={cn("inline-flex h-9 items-center gap-1 border-b w-full", className)} {...p} />;
export const TabsTrigger = ({ className, ...p }: React.ComponentProps<typeof TabsP.Trigger>) =>
  <TabsP.Trigger className={cn("relative -mb-px inline-flex h-9 items-center gap-1.5 border-b-2 border-transparent px-3 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground data-[state=active]:border-primary data-[state=active]:text-foreground [&_svg]:size-4", className)} {...p} />;
export const TabsContent = ({ className, ...p }: React.ComponentProps<typeof TabsP.Content>) => <TabsP.Content className={cn("pt-4 focus-visible:outline-none", className)} {...p} />;

export const Switch = ({ className, ...p }: React.ComponentProps<typeof SwitchP.Root>) => (
  <SwitchP.Root className={cn("peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors data-[state=checked]:bg-primary data-[state=unchecked]:bg-input", className)} {...p}>
    <SwitchP.Thumb className="pointer-events-none block size-4 rounded-full bg-white shadow-sm transition-transform data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0" /></SwitchP.Root>);

export const Progress = ({ value, className, tone = "bg-primary" }: { value: number; className?: string; tone?: string }) => (
  <ProgressP.Root value={value} className={cn("relative h-1.5 w-full overflow-hidden rounded-full bg-muted", className)}>
    <ProgressP.Indicator className={cn("h-full transition-all", tone)} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></ProgressP.Root>);

export function EmptyState({ icon: I, title, desc, action }: { icon?: React.ComponentType<{ className?: string }>; title: string; desc?: string; action?: React.ReactNode }) {
  return <div className="flex flex-col items-center justify-center py-14 text-center">
    {I && <div className="mb-3 flex size-10 items-center justify-center rounded-lg border bg-muted/50"><I className="size-5 text-muted-foreground" /></div>}
    <div className="text-sm font-medium">{title}</div>{desc && <div className="mt-1 max-w-sm text-xs text-muted-foreground">{desc}</div>}{action && <div className="mt-4">{action}</div>}</div>;
}
export const Kbd = ({ children }: { children: React.ReactNode }) => <kbd className="pointer-events-none inline-flex h-5 select-none items-center gap-0.5 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">{children}</kbd>;
