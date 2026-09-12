import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/format";

const control =
  "block w-full rounded-lg border border-line-strong bg-white px-3 py-1.5 text-sm text-slate-800 shadow-e1 " +
  "transition-[border-color,box-shadow] duration-150 placeholder:text-slate-400 " +
  "hover:border-slate-400 focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-500/12 " +
  "disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400";

export function Field({ label, hint, error, children, className }: {
  label: string; hint?: string; error?: string; children: React.ReactNode; className?: string;
}) {
  return (
    <label className={cn("block", className)}>
      <span className="mb-1.5 block text-xs font-medium text-slate-700">{label}</span>
      {children}
      {hint && !error && <span className="mt-1.5 block text-[11px] leading-relaxed text-muted">{hint}</span>}
      {error && <span className="mt-1.5 block text-[11px] font-medium text-rose-600">{error}</span>}
    </label>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cn(control, "h-9", props.className)} />;
}

export function Select({ options, placeholder, className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement> & {
  options: { value: string | number; label: string }[]; placeholder?: string;
}) {
  // Native select, custom chevron: the OS arrow is inconsistent across platforms and breaks the rhythm.
  return (
    <div className={cn("relative", className)}>
      <select {...props} className={cn(control, "h-9 cursor-pointer appearance-none pr-9")}>
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
    </div>
  );
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cn(control, "min-h-[84px] py-2 leading-relaxed", props.className)} />;
}
