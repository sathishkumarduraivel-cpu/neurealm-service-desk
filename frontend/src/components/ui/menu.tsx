import * as React from "react";
import * as DM from "@radix-ui/react-dropdown-menu";
import * as DialogP from "@radix-ui/react-dialog";
import * as PopP from "@radix-ui/react-popover";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export const DropdownMenu = DM.Root; export const DropdownMenuTrigger = DM.Trigger;
export const DropdownMenuContent = ({ className, sideOffset = 6, ...p }: React.ComponentProps<typeof DM.Content>) => <DM.Portal><DM.Content sideOffset={sideOffset} className={cn("z-50 min-w-[12rem] overflow-hidden rounded-lg border bg-popover p-1 text-popover-foreground shadow-pop animate-in fade-in-0 zoom-in-95", className)} {...p} /></DM.Portal>;
export const DropdownMenuItem = ({ className, ...p }: React.ComponentProps<typeof DM.Item>) => <DM.Item className={cn("relative flex cursor-default select-none items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent data-[disabled]:opacity-50 [&_svg]:size-4 [&_svg]:text-muted-foreground", className)} {...p} />;
export const DropdownMenuCheckboxItem = ({ className, children, ...p }: React.ComponentProps<typeof DM.CheckboxItem>) => <DM.CheckboxItem className={cn("relative flex cursor-default select-none items-center rounded-md py-1.5 ps-7 pe-2 text-sm outline-none focus:bg-accent", className)} {...p}><span className="absolute start-2 flex size-3.5 items-center justify-center"><DM.ItemIndicator>✓</DM.ItemIndicator></span>{children}</DM.CheckboxItem>;
export const DropdownMenuLabel = ({ className, ...p }: React.ComponentProps<typeof DM.Label>) => <DM.Label className={cn("px-2 py-1.5 text-xs font-medium text-muted-foreground", className)} {...p} />;
export const DropdownMenuSeparator = ({ className, ...p }: React.ComponentProps<typeof DM.Separator>) => <DM.Separator className={cn("-mx-1 my-1 h-px bg-border", className)} {...p} />;

export const Dialog = DialogP.Root; export const DialogTrigger = DialogP.Trigger; export const DialogTitle = DialogP.Title; export const DialogClose = DialogP.Close;
export function DialogContent({ className, children, hideClose, ...p }: React.ComponentProps<typeof DialogP.Content> & { hideClose?: boolean }) {
  return <DialogP.Portal><DialogP.Overlay className="fixed inset-0 z-50 bg-slate-950/40 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0" />
    <DialogP.Content className={cn("fixed start-1/2 top-[15%] z-50 w-full max-w-lg -translate-x-1/2 rounded-xl border bg-popover p-0 shadow-pop data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95", className)} {...p}>
      {children}{!hideClose && <DialogP.Close className="absolute end-3 top-3 rounded-md p-1 text-muted-foreground hover:bg-accent"><X className="size-4" /></DialogP.Close>}</DialogP.Content></DialogP.Portal>;
}
export const Popover = PopP.Root; export const PopoverTrigger = PopP.Trigger;
export const PopoverContent = ({ className, align = "end", sideOffset = 6, ...p }: React.ComponentProps<typeof PopP.Content>) => <PopP.Portal><PopP.Content align={align} sideOffset={sideOffset} className={cn("z-50 w-80 rounded-lg border bg-popover text-popover-foreground shadow-pop outline-none animate-in fade-in-0 zoom-in-95", className)} {...p} /></PopP.Portal>;
export const DropdownMenuSub = DM.Sub;
export const DropdownMenuSubTrigger = ({ className, ...p }: React.ComponentProps<typeof DM.SubTrigger>) => <DM.SubTrigger className={cn("flex cursor-default select-none items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-none focus:bg-accent data-[state=open]:bg-accent [&_svg]:size-4 [&_svg]:text-muted-foreground", className)} {...p} />;
export const DropdownMenuSubContent = ({ className, ...p }: React.ComponentProps<typeof DM.SubContent>) => <DM.Portal><DM.SubContent className={cn("z-50 min-w-[10rem] overflow-hidden rounded-lg border bg-popover p-1 text-popover-foreground shadow-pop", className)} {...p} /></DM.Portal>;
