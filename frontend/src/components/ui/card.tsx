import * as React from "react";
import { cn } from "@/lib/utils";
type D = React.HTMLAttributes<HTMLDivElement>;
export const Card = ({ className, ...p }: D) => <div className={cn("rounded-lg border bg-card text-card-foreground shadow-xs", className)} {...p} />;
export const CardHeader = ({ className, ...p }: D) => <div className={cn("flex items-start justify-between gap-3 px-5 pt-4 pb-3", className)} {...p} />;
export const CardTitle = ({ className, ...p }: D) => <div className={cn("text-sm font-semibold leading-none tracking-tight", className)} {...p} />;
export const CardDescription = ({ className, ...p }: D) => <div className={cn("mt-1.5 text-xs text-muted-foreground", className)} {...p} />;
export const CardContent = ({ className, ...p }: D) => <div className={cn("px-5 pb-5", className)} {...p} />;
