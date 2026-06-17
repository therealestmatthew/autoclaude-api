import { api } from "@/lib/api";

// Server component: pings /health. If it fails, the parent surface should
// still render; this component shows a banner inviting the operator to
// start the backend.

export async function ApiBanner() {
  try {
    const h = await api.health();
    if (h.ok) return null;
  } catch (e) {
    return (
      <div className="border border-rose-300 bg-rose-50 dark:bg-rose-950/30 dark:border-rose-900 text-rose-800 dark:text-rose-200 px-4 py-3 rounded-md text-sm">
        <strong>API unreachable</strong> at <code>{api.base}</code>. Start it
        with <code>uv run autoclaude-api</code>.
      </div>
    );
  }
  return null;
}
