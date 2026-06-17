import { api } from "@/lib/api";
import { StatCard } from "@/components/StatCard";
import { ApiBanner } from "@/components/ApiBanner";
import { Badge } from "@/components/Badge";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  let stats;
  let recent;
  try {
    [stats, recent] = await Promise.all([
      api.stats(),
      api.threads.recent({ limit: 10, days: 7 }),
    ]);
  } catch {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <ApiBanner />
      </div>
    );
  }

  const b = stats.stats.by_bucket;
  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Snapshot of the repo. {stats.stats.total} indexed documents.
        </p>
      </header>

      <section>
        <h2 className="text-sm uppercase tracking-wider text-zinc-500 mb-2">
          Buckets
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Catalog" value={b.catalog ?? 0} hint="reviewed assets" />
          <StatCard label="Queue" value={b.queue ?? 0} hint="pending review" />
          <StatCard
            label="Engagements"
            value={b.engagement ?? 0}
            hint="consulting"
          />
          <StatCard
            label="Plans"
            value={b.plan ?? 0}
            hint="design lineage"
          />
        </div>
      </section>

      <section>
        <h2 className="text-sm uppercase tracking-wider text-zinc-500 mb-2">
          Status
        </h2>
        <div className="flex flex-wrap gap-2">
          {Object.entries(stats.stats.by_status).map(([k, v]) => (
            <div
              key={k}
              className="flex items-center gap-2 px-3 py-1.5 border border-zinc-200 dark:border-zinc-800 rounded-md text-sm"
            >
              <Badge variant="status">{k}</Badge>
              <span className="font-mono text-zinc-600 dark:text-zinc-300">
                {v}
              </span>
            </div>
          ))}
          {stats.stats.with_issues > 0 && (
            <div className="flex items-center gap-2 px-3 py-1.5 border border-rose-200 dark:border-rose-900 bg-rose-50 dark:bg-rose-950/30 rounded-md text-sm">
              <Badge variant="issue">issues</Badge>
              <span className="font-mono">{stats.stats.with_issues}</span>
            </div>
          )}
        </div>
      </section>

      <section>
        <div className="flex items-baseline justify-between mb-2">
          <h2 className="text-sm uppercase tracking-wider text-zinc-500">
            Recent threads
          </h2>
          <Link
            href="/threads"
            className="text-sm text-brand-700 dark:text-brand-100 hover:underline"
          >
            View all
          </Link>
        </div>
        {recent.events.length === 0 ? (
          <div className="text-sm text-zinc-500">
            No recent thread events. Run <code>uv run scout run</code>.
          </div>
        ) : (
          <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg overflow-hidden">
            {recent.events.map((e, i) => (
              <div
                key={`${e.thread_id ?? ""}-${i}`}
                className="flex items-center gap-3 px-4 py-2 border-b last:border-b-0 border-zinc-200 dark:border-zinc-800"
              >
                <span className="text-xs text-zinc-500 w-24 shrink-0 font-mono">
                  {e.date}
                </span>
                <span className="text-sm font-medium w-40 shrink-0 truncate">
                  {e.agent ?? "—"}
                </span>
                {e.outcome && <Badge variant="status">{e.outcome}</Badge>}
                <span className="text-sm text-zinc-600 dark:text-zinc-300 truncate flex-1">
                  {e.summary ?? ""}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
