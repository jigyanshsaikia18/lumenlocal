import type { CitedSource } from "@/lib/geo/types";

interface CitedSourcesListProps {
  sources: CitedSource[];
}

/**
 * Ranked list of third-party sources the AI referenced (GEO-5), so the
 * agency knows where to invest (reviews, directories, local press, etc).
 */
export function CitedSourcesList({ sources }: CitedSourcesListProps) {
  const ranked = [...sources].sort((a, b) => b.citations - a.citations);
  const max = ranked[0]?.citations ?? 1;

  if (ranked.length === 0) {
    return <p className="text-sm text-muted">No sources cited in the latest scan.</p>;
  }

  return (
    <ul className="flex flex-col gap-2">
      {ranked.map((s) => (
        <li key={s.source} className="flex items-center gap-3">
          <span className="w-32 shrink-0 truncate text-sm text-foreground">{s.source}</span>
          <div className="h-2 flex-1 rounded-full bg-gray-100">
            <div
              className="h-2 rounded-full bg-violet-500"
              style={{ width: `${Math.max(4, (s.citations / max) * 100)}%` }}
            />
          </div>
          <span className="w-8 shrink-0 text-right text-xs text-muted">{s.citations}</span>
        </li>
      ))}
    </ul>
  );
}
