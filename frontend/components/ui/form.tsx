import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/format";

const control =
  "block w-full rounded-lg border border-line-strong bg-panel px-3 py-1.5 text-sm text-ink shadow-[0_1px_2px_rgba(16,34,42,0.04)] " +
  "transition-[border-color,box-shadow,background] duration-150 placeholder:text-faint " +
  "hover:border-[#b9c5cb] focus:border-accent focus:outline-none focus:ring-3 focus:ring-accent/15 " +
  "disabled:cursor-not-allowed disabled:bg-sunken disabled:opacity-60";

export function Field({ label, hint, error, children, className }: {
  label: string; hint?: string; error?: string; children: React.ReactNode; className?: string;
}) {
  return (
    <label className={cn("block", className)}>
      <span className="mb-1.5 block text-[13px] font-medium text-ink-2">{label}</span>
      {children}
      {hint && !error && <span className="mt-1.5 block text-xs leading-relaxed text-muted">{hint}</span>}
      {error && <span className="mt-1.5 block text-xs font-medium text-high">{error}</span>}
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
