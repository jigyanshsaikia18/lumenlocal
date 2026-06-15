"use client";

export interface FeatureToggleRowProps {
  featureKey: string;
  featureName: string;
  enabled: boolean;
  source: string;
  onToggle: (key: string, newState: boolean) => void;
}

const SOURCE_LABELS: Record<string, string> = {
  location: "Location",
  client: "Client",
  plan: "Plan",
  default: "Default",
  dependency: "Dep. off",
};

export function FeatureToggleRow({
  featureKey,
  featureName,
  enabled,
  source,
  onToggle,
}: FeatureToggleRowProps) {
  const isOverridden = source !== "default";

  return (
    <div className="flex items-center justify-between border-b border-hairline px-4 py-3 last:border-0">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">{featureName}</p>
        <p className="mt-0.5 font-mono text-xs text-muted">{featureKey}</p>
      </div>

      <div className="flex items-center gap-3">
        <span
          className={[
            "rounded-full px-2 py-0.5 text-xs font-medium",
            isOverridden
              ? "bg-brand/10 text-brand"
              : "bg-muted/20 text-muted",
          ].join(" ")}
        >
          {SOURCE_LABELS[source] ?? source}
        </span>

        <button
          role="switch"
          aria-checked={enabled}
          aria-label={featureName}
          onClick={() => onToggle(featureKey, !enabled)}
          className={[
            "relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full",
            "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand",
            enabled ? "bg-brand" : "bg-gray-300",
          ].join(" ")}
        >
          <span
            className={[
              "inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform",
              enabled ? "translate-x-6" : "translate-x-1",
            ].join(" ")}
          />
        </button>
      </div>
    </div>
  );
}
