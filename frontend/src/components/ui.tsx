// Small shared presentation components. No API calls here.
import { useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from "react";

import { describeError } from "../lib/errors";
import type { FeatureInfo } from "../lib/features";

type Variant = "primary" | "secondary" | "ghost" | "danger";

export function Button({
  variant = "primary",
  busy = false,
  children,
  className = "",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; busy?: boolean }) {
  return (
    <button
      className={`btn btn-${variant} ${className}`}
      aria-busy={busy || undefined}
      disabled={busy || rest.disabled}
      {...rest}
    >
      {busy && <span className="spinner" aria-hidden="true" />}
      {children}
    </button>
  );
}

export function TextField({
  label,
  hint,
  error,
  ...input
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string; error?: string | null }) {
  const id = useId();
  const describedBy = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(" ") || undefined;
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {hint && (
        <p id={`${id}-hint`} className="field-hint">
          {hint}
        </p>
      )}
      <input id={id} aria-invalid={error ? true : undefined} aria-describedby={describedBy} {...input} />
      {error && (
        <p id={`${id}-error`} className="field-error">
          {error}
        </p>
      )}
    </div>
  );
}

type Tone = "info" | "success" | "warning" | "danger";
const TONE_ICON: Record<Tone, string> = { info: "ⓘ", success: "✔", warning: "⚠", danger: "✖" };

export function Alert({ tone = "info", title, children, role }: { tone?: Tone; title?: string; children?: ReactNode; role?: "alert" | "status" }) {
  return (
    <div className={`alert alert-${tone}`} role={role ?? (tone === "danger" ? "alert" : "status")}>
      <span className="alert-icon" aria-hidden="true">
        {TONE_ICON[tone]}
      </span>
      <div>
        {title && <p className="alert-title">{title}</p>}
        {children && <div className="alert-body">{children}</div>}
      </div>
    </div>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <span className="spinner spinner-lg" aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state state-empty">
      <p className="state-title">{title}</p>
      {children && <div className="state-body">{children}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { title, message, retryable } = describeError(error);
  return (
    <Alert tone="danger" title={title}>
      <p>{message}</p>
      {retryable && onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
    </Alert>
  );
}

/** Honest "not connected yet" state for features whose backend lands in a later phase. */
export function FeatureUnavailable({ feature, children }: { feature: FeatureInfo; children?: ReactNode }) {
  return (
    <section className="unavailable" aria-label="Feature availability">
      <span className="badge badge-neutral">Not yet connected · planned for Phase {feature.phase}</span>
      <p className="unavailable-title">{feature.description}: not available in this build</p>
      <p>
        This screen is ready, but the backend service it needs ({feature.endpoints.join(", ")}) hasn't been implemented yet.
        Nothing here is simulated: no data is sent and no results are invented.
      </p>
      {children}
    </section>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {description && <p className="page-description">{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

export type BadgeTone = "success" | "warning" | "danger" | "info" | "neutral";

/** Status pill: always icon + text, never color alone (NFR-015). */
export function StatusBadge({ label, tone, icon }: { label: string; tone: BadgeTone; icon: string }) {
  return (
    <span className={`badge badge-${tone}`}>
      <span aria-hidden="true">{icon}</span> {label}
    </span>
  );
}
