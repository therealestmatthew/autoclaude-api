import { api } from "@/lib/api";
import { AssetCard } from "@/components/AssetCard";
import { ApiBanner } from "@/components/ApiBanner";

export const dynamic = "force-dynamic";

export default async function CatalogPage({
  searchParams,
}: {
  searchParams: Promise<{ kind?: string; status?: string; q?: string }>;
}) {
  const sp = await searchParams;
  let list;
  try {
    list = await api.catalog.list({
      kind: sp.kind,
      status: sp.status,
      q: sp.q,
      limit: 200,
    });
  } catch {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Catalog</h1>
        <ApiBanner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Catalog</h1>
          <p className="text-sm text-zinc-500 mt-1">
            {list.total} assets. The master DB of polymorphic, reviewed content.
          </p>
        </div>
        <form className="flex items-center gap-2">
          <input
            type="text"
            name="q"
            placeholder="search slug, title, tags"
            defaultValue={sp.q ?? ""}
            className="px-3 py-1.5 text-sm border border-zinc-200 dark:border-zinc-800 rounded-md bg-white dark:bg-zinc-950 w-64"
          />
        </form>
      </header>

      <div className="flex flex-wrap gap-2 text-xs">
        <FilterLink label="all" current={sp.kind} param="kind" />
        {["agent", "skill", "plugin", "mcp", "repo", "article", "org"].map((k) => (
          <FilterLink key={k} label={k} value={k} current={sp.kind} param="kind" />
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {list.items.map((a) => (
          <AssetCard key={a.path} asset={a} hrefPrefix="/catalog" />
        ))}
      </div>
      {list.items.length === 0 && (
        <div className="text-sm text-zinc-500">No assets match.</div>
      )}
    </div>
  );
}

function FilterLink({
  label,
  value,
  current,
  param,
}: {
  label: string;
  value?: string;
  current?: string;
  param: string;
}) {
  const isActive = (value ?? "") === (current ?? "");
  const url = value ? `/catalog?${param}=${value}` : "/catalog";
  return (
    <a
      href={url}
      className={`px-2.5 py-1 rounded-md border ${
        isActive
          ? "border-brand-500 bg-brand-50 dark:bg-zinc-800 text-brand-700 dark:text-zinc-100"
          : "border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 hover:border-zinc-400"
      }`}
    >
      {label}
    </a>
  );
}
