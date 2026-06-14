interface ScoreRingProps {
  /** 0–100. */
  value: number;
  grade: string;
  size?: number;
}

/**
 * Circular progress gauge for the health score, stroked with the brand gradient
 * for a premium feel. Pure SVG — no dependencies, crisp at any size.
 */
export function ScoreRing({ value, grade, size = 132 }: ScoreRingProps) {
  const clamped = Math.max(0, Math.min(100, value));
  const stroke = 10;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const dash = (clamped / 100) * circumference;

  return (
    <div
      className="relative shrink-0"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Health score ${Math.round(clamped)} out of 100, grade ${grade}`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id="ll-score-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="rgb(var(--ll-brand))" />
            <stop offset="100%" stopColor="rgb(var(--ll-accent))" />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgb(var(--ll-hairline))"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="url(#ll-score-gradient)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference - dash}`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-semibold tabular-nums text-foreground">
          {Math.round(clamped)}
        </span>
        <span className="text-xs font-medium uppercase tracking-wide text-muted">
          Grade {grade}
        </span>
      </div>
    </div>
  );
}
