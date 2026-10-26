import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
export const badgeVariants = cva("inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-4 whitespace-nowrap", {
  variants: { tone: {
    neutral: "border-slate-200 bg-slate-50 text-slate-700",
    brand: "border-indigo-200 bg-indigo-50 text-indigo-700",
    blue: "border-sky-200 bg-sky-50 text-sky-700",
    green: "border-emerald-200 bg-emerald-50 text-emerald-700",
    amber: "border-amber-200 bg-amber-50 text-amber-800",
    orange: "border-orange-200 bg-orange-50 text-orange-800",
    red: "border-red-200 bg-red-50 text-red-700",
    violet: "border-violet-200 bg-violet-50 text-violet-700",
    solidRed: "border-transparent bg-red-600 text-white" } },
  defaultVariants: { tone: "neutral" } });
export type Tone = NonNullable<VariantProps<typeof badgeVariants>["tone"]>;
export const Badge = ({ className, tone, ...p }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) => <span className={cn(badgeVariants({ tone }), className)} {...p} />;
export const Dot = ({ tone = "neutral" }: { tone?: Tone }) => {
  const c: Record<string, string> = { neutral: "bg-slate-400", brand: "bg-indigo-500", blue: "bg-sky-500", green: "bg-emerald-500", amber: "bg-amber-500", orange: "bg-orange-500", red: "bg-red-500", violet: "bg-violet-500", solidRed: "bg-white" };
  return <span className={cn("size-1.5 rounded-full", c[tone])} />;
};
