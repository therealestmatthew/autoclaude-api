import { api } from "@/lib/api";
import { ProposalCard } from "@/components/ProposalCard";

export const dynamic = "force-dynamic";

type Search = { [k: string]: string | string[] | undefined };

function pick(s: Search, k: string): string | undefined {
  const v = s[k];
  return Array.isArray(v) ? v[0] : v;
}

export default async function ProposalsInbox({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  const params = await searchParams;
  const status = pick(params, "status") ?? "pending";
  const source = pick(params, "source");
  const bucket = pick(params, "bucket");
  const sort = pick(params, "sort") ?? "created";

  let list;
  try {
    list = await api.proposals.list({
      status,
      source,
      target_bucket: bucket,
      limit: 500,
    });
  } catch (e) {
    return (
      <div className="space-y-3">
        <h1 className="text-2xl font-semibold">Proposals</h1>
        <div className="rounded border border-rose-300 bg-rose-50 dark:bg-rose-950 dark:border-rose-800 p-3 text-sm text-rose-900 dark:text-rose-200">
          Failed to load proposals: {e instanceof Error ? e.message : String(e)}
        </div>
      </div>
    );
  }

  const items = [...list.items];
  if (sort === "confidence") {
    items.sort((a, b) => (b.confidence ?? -1) - (a.confidence ?? -1));
  } else {
    items.sort((a, b) => b.created_at - a.created_at);
  }

  return (
    <div className="space-y-4">
      <header className="flex items-baseline justify-between gap-4">
        <h1 className="text-2xl font-semibold">Proposals</h1>
        <span className="text-xs text-zinc-500">{list.total} total</span>
      </header>

      <Filters status={status} source={source} bucket={bucket} sort={sort} />

      {items.length === 0 ? (
        <p className="text-sm text-zinc-500">No proposals match these filters.</p>
      ) : (
        <div className="space-y-2">
          {items.map((p) => (
            <ProposalCard key={p.id} proposal={p} />
          ))}
        </div>
      )}
    </div>
  );
}

function Filters({
  status,
  source,
  bucket,
  sort,
}: {
  status: string;
  source: string | undefined;
  bucket: string | undefined;
  sort: string;
}) {
  return (
    <form className="flex flex-wrap items-end gap-3 border border-zinc-200 dark:border-zinc-800 rounded p-3 text-sm">
      <label className="block">
        <span className="block text-xs uppercase tracking-wider text-zinc-500 mb-1">
          status
        </span>
        <select name="status" defaultValue={status} className="form-input">
          {["pending", "accepted", "rejected", "expired", "superseded", "all"].map(
            (s) => (
              <option key={s} value={s === "all" ? "" : s}>
                {s}
              </option>
            ),
          )}
        </select>
      </label>
      <label className="block">
        <span className="block text-xs uppercase tracking-wider text-zinc-500 mb-1">
          source
        </span>
        <select name="source" defaultValue={source ?? ""} className="form-input">
          <option value="">any</option>
          <option value="operator">operator</option>
          <option value="reviewer-agent">reviewer-agent</option>
        </select>
      </label>
      <label className="block">
        <span className="block text-xs uppercase tracking-wider text-zinc-500 mb-1">
          bucket
        </span>
        <select name="bucket" defaultValue={bucket ?? ""} className="form-input">
          <option value="">any</option>
          <option value="queue">queue</option>
          <option value="catalog">catalog</option>
        </select>
      </label>
      <label className="block">
        <span className="block text-xs uppercase tracking-wider text-zinc-500 mb-1">
          sort
        </span>
        <select name="sort" defaultValue={sort} className="form-input">
          <option value="created">newest first</option>
          <option value="confidence">confidence ↓</option>
        </select>
      </label>
      <button
        type="submit"
        className="rounded bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700"
      >
        Apply
      </button>
    </form>
  );
}
