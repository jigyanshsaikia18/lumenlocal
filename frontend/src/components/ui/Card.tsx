import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
}

/** Premium surface primitive: hairline border, soft layered shadow, rounded. */
export function Card({ children, className = "" }: CardProps) {
  return (
    <section
      className={`rounded-2xl border border-hairline bg-surface shadow-card transition-shadow duration-200 hover:shadow-card-hover ${className}`}
    >
      {children}
    </section>
  );
}

interface CardHeaderProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}

export function CardHeader({ title, subtitle, action }: CardHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 px-6 pt-6">
      <div>
        <h2 className="text-base font-semibold tracking-tight text-foreground">{title}</h2>
        {subtitle ? <p className="mt-0.5 text-sm text-muted">{subtitle}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
