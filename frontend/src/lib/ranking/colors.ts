/**
 * Maps a numeric map-pack rank to a Tailwind bg/text class pair.
 * Color scale mirrors the LocateX geo-grid convention:
 *   #1      → deep green  (most visible)
 *   #2–3    → green
 *   #4–7    → amber/yellow
 *   #8–10   → orange
 *   #11–20  → red (fading visibility)
 *   null/>20→ neutral gray (unranked)
 */
export function rankColorClass(rank: number | null): {
  bg: string;
  text: string;
  label: string;
} {
  if (rank === null || rank > 20) {
    return { bg: "bg-gray-100", text: "text-gray-400", label: "unranked" };
  }
  if (rank === 1) {
    return { bg: "bg-green-600", text: "text-white", label: "#1" };
  }
  if (rank <= 3) {
    return { bg: "bg-green-400", text: "text-white", label: `#${rank}` };
  }
  if (rank <= 7) {
    return { bg: "bg-amber-400", text: "text-white", label: `#${rank}` };
  }
  if (rank <= 10) {
    return { bg: "bg-orange-500", text: "text-white", label: `#${rank}` };
  }
  if (rank <= 15) {
    return { bg: "bg-red-400", text: "text-white", label: `#${rank}` };
  }
  return { bg: "bg-red-700", text: "text-white", label: `#${rank}` };
}
