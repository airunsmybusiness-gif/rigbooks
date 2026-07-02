/** Small UI kit: cards, buttons, inputs, tables, stat tiles, modals. */
import { X } from "lucide-react";
import { useEffect, type ReactNode } from "react";

export function cx(...parts: (string | false | undefined | null)[]) {
  return parts.filter(Boolean).join(" ");
}

export function Card({ children, className, title, action }: {
  children: ReactNode; className?: string; title?: ReactNode; action?: ReactNode;
}) {
  return (
    <section className={cx(
      "rounded-2xl border border-line bg-surface-1 shadow-sm", className)}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 px-5 pt-4">
          <h3 className="text-sm font-semibold text-ink-2">{title}</h3>
          {action}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

export function StatCard({ label, value, delta, sub, tone }: {
  label: string; value: string; delta?: string; sub?: string;
  tone?: "good" | "bad" | "neutral";
}) {
  return (
    <div className="rounded-2xl border border-line bg-surface-1 p-5 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-3">{label}</p>
      <p className="mt-1.5 text-xl font-semibold leading-none text-ink-1 sm:text-[26px]">{value}</p>
      {(delta || sub) && (
        <p className={cx("mt-2 text-xs",
          tone === "good" ? "text-good" : tone === "bad" ? "text-bad" : "text-ink-3")}>
          {delta}{delta && sub ? " · " : ""}{sub}
        </p>
      )}
    </div>
  );
}

const btnBase =
  "inline-flex items-center justify-center gap-1.5 rounded-xl text-sm font-medium " +
  "transition-colors focus-visible:outline-2 focus-visible:outline-accent " +
  "disabled:opacity-50 disabled:pointer-events-none";

export function Button({ children, onClick, variant = "primary", type = "button",
  className, disabled, title }: {
  children: ReactNode; onClick?: () => void;
  variant?: "primary" | "ghost" | "danger" | "outline";
  type?: "button" | "submit"; className?: string; disabled?: boolean; title?: string;
}) {
  const styles = {
    primary: "bg-accent text-white hover:opacity-90 px-4 py-2",
    outline: "border border-line text-ink-1 hover:bg-surface-2 px-4 py-2",
    ghost: "text-ink-2 hover:bg-surface-2 px-3 py-2",
    danger: "text-bad hover:bg-bad/10 px-3 py-2",
  }[variant];
  return (
    <button type={type} onClick={onClick} disabled={disabled} title={title}
      className={cx(btnBase, styles, className)}>
      {children}
    </button>
  );
}

const fieldBase =
  "w-full rounded-xl border border-line bg-surface-2 px-3 py-2 text-sm text-ink-1 " +
  "placeholder:text-ink-3 focus:outline-2 focus:outline-accent";

export function Field({ label, children, className }: {
  label: string; children: ReactNode; className?: string;
}) {
  return (
    <label className={cx("block", className)}>
      <span className="mb-1 block text-xs font-medium text-ink-2">{label}</span>
      {children}
    </label>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(fieldBase, props.className)} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cx(fieldBase, "appearance-none", props.className)} />;
}

export function Badge({ children, tone = "neutral" }: {
  children: ReactNode; tone?: "good" | "bad" | "warn" | "neutral" | "accent";
}) {
  const styles = {
    good: "bg-good/10 text-good",
    bad: "bg-bad/10 text-bad",
    warn: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    accent: "bg-accent-soft text-accent",
    neutral: "bg-surface-2 text-ink-2",
  }[tone];
  return (
    <span className={cx("inline-flex rounded-full px-2 py-0.5 text-xs font-medium", styles)}>
      {children}
    </span>
  );
}

export function Table({ head, children }: { head: ReactNode; children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-line">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line bg-surface-2 text-left text-xs uppercase tracking-wide text-ink-3">
            {head}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  );
}

export const Th = ({ children, right }: { children?: ReactNode; right?: boolean }) => (
  <th className={cx("px-3 py-2.5 font-medium", right && "text-right")}>{children}</th>
);
export const Td = ({ children, right, className }: {
  children?: ReactNode; right?: boolean; className?: string;
}) => (
  <td className={cx("px-3 py-2.5 text-ink-1", right && "text-right tabular-nums", className)}>
    {children}
  </td>
);

export function Modal({ title, onClose, children, wide }: {
  title: string; onClose: () => void; children: ReactNode; wide?: boolean;
}) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={cx(
        "fade-up max-h-[90vh] w-full overflow-y-auto rounded-2xl border border-line bg-surface-1 p-6 shadow-xl",
        wide ? "max-w-3xl" : "max-w-lg")}>
        <header className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-ink-1">{title}</h2>
          <Button variant="ghost" onClick={onClose} title="Close"><X size={18} /></Button>
        </header>
        {children}
      </div>
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-axis px-6 py-10 text-center text-sm text-ink-3">
      {children}
    </div>
  );
}

export function PageHeader({ title, sub, action }: {
  title: string; sub?: string; action?: ReactNode;
}) {
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-ink-1">{title}</h1>
        {sub && <p className="mt-0.5 text-sm text-ink-3">{sub}</p>}
      </div>
      {action}
    </header>
  );
}
