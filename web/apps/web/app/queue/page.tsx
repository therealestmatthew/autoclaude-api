import { api } from "@/lib/api";
import { AssetCard } from "@/components/AssetCard";
import { ApiBanner } from "@/components/ApiBanner";

const STATIC_MODE = process.env.NEXT_PUBLIC_STATIC_MODE === "true";

export default async function QueuePage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  if (STATIC_MODE) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Queue</h1>
        <p className="text-sm text-zinc-500">The scout queue is not part of the static export.</p>
      </div>
    );
  }
  const sp = await searchParams;
  let list;
  try {
    list = await api.queue.list({ q: sp.q, limit: 200 });
  } catch {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Queue</h1>
        <ApiBanner />
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Scout queue</h1>
          <p className="text-sm text-zinc-500 mt-1">
            {list.total} candidates awaiting human review.
          </p>
        </div>
        <form>
          <input
            type="text"
            name="q"
            placeholder="search"
            defaultValue={sp.q ?? ""}
            className="px-3 py-1.5 text-sm border border-zinc-200 dark:border-zinc-800 rounded-md bg-white dark:bg-zinc-950 w-64"
          />
        </form>
      </header>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {list.items.map((a) => (
          <AssetCard key={a.path} asset={a} hrefPrefix="/queue" />
        ))}
      </div>
      {list.items.length === 0 && (
        <div className="text-sm text-zinc-500">
          Queue is empty. Run <code>uv run scout run</code> to populate it.
        </div>
      )}
    </div>
  );
}
