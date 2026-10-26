import * as React from "react";
import { cn } from "@/lib/utils";
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) => <input ref={ref} className={cn("input", className)} {...p} />);
Input.displayName = "Input";
export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...p }, ref) => <textarea ref={ref} className={cn("input min-h-[96px] py-2", className)} {...p} />);
Textarea.displayName = "Textarea";
export const NativeSelect = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(({ className, ...p }, ref) => (
  <select ref={ref} className={cn("input appearance-none bg-[length:16px] bg-[right_0.6rem_center] bg-no-repeat pe-8", className)}
    style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")" }} {...p} />
));
NativeSelect.displayName = "NativeSelect";
export const Label = ({ className, ...p }: React.LabelHTMLAttributes<HTMLLabelElement>) => <label className={cn("mb-1.5 block text-xs font-medium text-foreground/80", className)} {...p} />;
export const FieldError = ({ msg }: { msg?: string }) => (msg ? <p className="mt-1 text-xs text-destructive">{msg}</p> : null);
