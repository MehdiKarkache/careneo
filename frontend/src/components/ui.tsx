import { LoaderCircle } from "lucide-react";
import type { ButtonHTMLAttributes, ComponentType, ReactNode } from "react";
import type { BookingStatus } from "../api/client";
import { BOOKING_STATUS, SLOT_STATUS, type Tone } from "../lib/format";

const BUTTON_VARIANTS = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 focus-visible:outline-brand-600",
  success: "bg-emerald-600 text-white hover:bg-emerald-700 focus-visible:outline-emerald-600",
  danger: "bg-rose-600 text-white hover:bg-rose-700 focus-visible:outline-rose-600",
  secondary: "bg-white text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50",
  ghost: "text-slate-600 hover:bg-slate-100",
};

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof BUTTON_VARIANTS;
  loading?: boolean;
};

export function Button({ variant = "primary", loading = false, className = "", children, disabled, type = "button", ...props }: ButtonProps) {
  return (
    <button
      {...props}
      type={type}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-semibold shadow-xs transition focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60 ${BUTTON_VARIANTS[variant]} ${className}`}
    >
      {loading && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function Card({ className = "", children }: { className?: string; children: ReactNode }) {
  return <div className={`rounded-xl bg-white shadow-xs ring-1 ring-slate-200 ${className}`}>{children}</div>;
}

const TONES: Record<Tone, string> = {
  amber: "bg-amber-50 text-amber-800 ring-amber-600/25",
  emerald: "bg-emerald-50 text-emerald-700 ring-emerald-600/25",
  rose: "bg-rose-50 text-rose-700 ring-rose-600/25",
  slate: "bg-slate-100 text-slate-600 ring-slate-500/25",
  sky: "bg-sky-50 text-sky-700 ring-sky-600/25",
  indigo: "bg-indigo-50 text-indigo-700 ring-indigo-600/25",
};

export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${TONES[tone]}`}>
      {children}
    </span>
  );
}

export function BookingStatusBadge({ status }: { status: BookingStatus }) {
  return <Badge tone={BOOKING_STATUS[status].tone}>{BOOKING_STATUS[status].label}</Badge>;
}

export function SlotStatusBadge({ status }: { status: keyof typeof SLOT_STATUS }) {
  return <Badge tone={SLOT_STATUS[status].tone}>{SLOT_STATUS[status].label}</Badge>;
}

export const inputClass =
  "block w-full rounded-lg border-0 bg-white px-3 py-2 text-sm text-slate-900 shadow-xs ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-brand-500 aria-invalid:ring-rose-400";

export function Field({ label, error, hint, className = "", children }: { label: string; error?: string; hint?: string; className?: string; children: ReactNode }) {
  return (
    <label className={`block space-y-1.5 ${className}`}>
      <span className="text-sm font-medium text-slate-700">{label}</span>
      {children}
      {error ? <span className="block text-xs text-rose-600">{error}</span> : hint && <span className="block text-xs text-slate-500">{hint}</span>}
    </label>
  );
}

export function Spinner({ label = "Chargement…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-slate-500" role="status">
      <LoaderCircle className="size-5 animate-spin" aria-hidden />
      {label}
    </div>
  );
}

export function ErrorNotice({ error }: { error: Error | null | undefined }) {
  if (!error) return null;
  return (
    <div role="alert" className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700 ring-1 ring-rose-200">
      {error.message}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children }: { icon: ComponentType<{ className?: string }>; title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border-2 border-dashed border-slate-200 px-6 py-12 text-center">
      <Icon className="mx-auto size-8 text-slate-300" />
      <p className="mt-3 font-medium text-slate-700">{title}</p>
      {children && <div className="mt-1 text-sm text-slate-500">{children}</div>}
    </div>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Tabs<T extends string | undefined>({ value, options, onChange }: { value: T; options: { value: T; label: string; count?: number }[]; onChange: (value: T) => void }) {
  return (
    <div className="mb-5 flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1" role="tablist">
      {options.map((option) => (
        <button
          key={option.label}
          type="button"
          role="tab"
          aria-selected={option.value === value}
          onClick={() => onChange(option.value)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${option.value === value ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"}`}
        >
          {option.label}
          {option.count !== undefined && <span className="ml-1.5 text-xs text-slate-400">{option.count}</span>}
        </button>
      ))}
    </div>
  );
}
