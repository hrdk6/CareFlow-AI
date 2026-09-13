import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/format";

const control =
  "block w-full rounded-md border border-line-strong bg-sunken px-3 py-1.5 text-sm text-ink " +
  "transition-[border-color,box-shadow,background] duration-150 placeholder:text-faint " +
  "hover:border-[#3d3d41] focus:border-accent focus:bg-panel focus:outline-none focus:ring-2 focus:ring-accent/25 " +
  "disabled:cursor-not-allowed disabled:opacity-50";

export function Field({ label, hint, error, children, className }: {
  label: string; hint?: string; error?: string; children: React.ReactNode; className?: string;
}) {
  return (
    <label className={cn("block", className)}>
      <span className="mb-1.5 block font-display text-[11px] font-semibold uppercase tracking-[0.1em] text-muted">{label}</span>
      {children}
      {hint && !error && <span className="mt-1.5 block text-[11px] leading-relaxed text-muted">{hint}</span>}
      {error && <span className="mt-1.5 block text-[11px] font-medium text-high">{error}</span>}
    </label>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cn(control, "h-9", props.className)} />;
}

export function Select({ options, placeholder, className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement> & {
  options: { value: string | number; label: string }[]; placeholder?: string;
}) {
  // Native select, drawn chevron: the OS arrow ignores the palette and the control rhythm.
  return (
    <div className={cn("relative", className)}>
      <select {...props} className={cn(control, "h-9 cursor-pointer appearance-none pr-9")}>
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
    </div>
  );
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cn(control, "min-h-[84px] py-2 leading-relaxed", props.className)} />;
}
