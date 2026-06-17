import { api } from "@/lib/api";
import { ApiBanner } from "@/components/ApiBanner";
import { Badge } from "@/components/Badge";

export const dynamic = "force-dynamic";

export default async function ThreadsPage({
  searchParams,
}: {
  searchParams: Promise<{ since?: string; until?: string; agent?: string }>;
}) {
  const sp = await searchParams;
  let list;
  try {
    list = await api.threads.list({
      since: sp.since,
      until: sp.until,
      agent: sp.agent,
      limit: 500,
    });
  } catch {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Threads</h1>
        <ApiBanner />
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Threads</h1>
          <p className="text-sm text-zinc-500 mt-1">
            {list.total} event{list.total === 1 ? "" : "s"} across{" "}
            {list.days_scanned} day{list.days_scanned === 1 ? "" : "s"}.
          </p>
        </div>
        <form className="flex items-center gap-2">
          <input
            type="date"
            name="since"
            defaultValue={sp.since ?? ""}
            className="px-2 py-1 text-sm border border-zinc-200 dark:border-zinc-800 rounded-md bg-white dark:bg-zinc-950"
          />
          <input
            type="date"
            name="until"
            defaultValue={sp.until ?? ""}
            className="px-2 py-1 text-sm border border-zinc-200 dark:border-zinc-800 rounded-md bg-white dark:bg-zinc-950"
          />
          <input
            type="text"
            name="agent"
            placeholder="agent"
            defaultValue={sp.agent ?? ""}
            className="px-2 py-1 text-sm border border-zinc-200 dark:border-zinc-800 rounded-md bg-white dark:bg-zinc-950 w-32"
          />
        </form>
      </header>
      <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg overflow-hidden">
        {list.events.length === 0 ? (
          <div className="p-4 text-sm text-zinc-500">No thread events.</div>
        ) : (
          list.events.map((e, i) => (
            <div
              key={`${e.thread_id ?? ""}-${i}`}
              className="flex items-center gap-3 px-4 py-2 border-b last:border-b-0 border-zinc-200 dark:border-zinc-800 text-sm"
            >
              <span className="text-xs text-zinc-500 w-24 shrink-0 font-mono">
                {e.date}
              </span>
              <span className="font-medium w-40 shrink-0 truncate">
                {e.agent ?? "—"}
              </span>
              {e.outcome && <Badge variant="status">{e.outcome}</Badge>}
              <span className="text-zinc-600 dark:text-zinc-300 truncate flex-1">
                {e.summary ?? ""}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
