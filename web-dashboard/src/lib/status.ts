// Shared status color classes so badges/indicators stay consistent everywhere.
// Values are copied verbatim from the original inline usages to keep the exact
// same appearance in light and dark themes.

export const STATUS_COLORS = {
  success: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  warn: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  danger: "bg-rose-500/10 text-rose-500 border-rose-500/20",
} as const;

// Freshness (fresh / stale / offline) -> color class.
export function freshnessColor(status: string | undefined): string {
  if (status === "fresh") return STATUS_COLORS.success;
  if (status === "stale") return STATUS_COLORS.warn;
  return STATUS_COLORS.danger;
}
