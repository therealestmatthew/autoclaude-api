// Small display helpers — date formatting, status badge colors, etc.

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return iso;
}

export function statusColor(status: string | null | undefined): string {
  switch (status) {
    case "active":
    case "adopted":
    case "reviewed":
      return "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200";
    case "draft":
      return "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200";
    case "archived":
    case "retired":
    case "stale":
      return "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
    case "done":
      return "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200";
    case "prospecting":
    case "paused":
      return "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200";
    default:
      return "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
  }
}

export function bucketLabel(bucket: string): string {
  const map: Record<string, string> = {
    catalog: "Catalog",
    queue: "Queue",
    engagement: "Engagement",
    convention: "Convention",
    plan: "Plan",
    runbook: "Runbook",
    readme: "README",
    claude: "Toolkit",
    consulting: "Consulting",
    session_prompt: "Session prompt",
    other: "Other",
  };
  return map[bucket] ?? bucket;
}
