import { api } from "@/lib/api";
import { AssetCard } from "@/components/AssetCard";
import { ApiBanner } from "@/components/ApiBanner";

export const dynamic = "force-dynamic";

export default async function EngagementsPage() {
  let list;
  try {
    list = await api.engagements.list();
  } catch {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Engagements</h1>
        <ApiBanner />
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Engagements</h1>
        <p className="text-sm text-zinc-500 mt-1">
          {list.total} consulting engagement{list.total === 1 ? "" : "s"}.
        </p>
      </header>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {list.items.map((a) => (
          <AssetCard key={a.path} asset={a} hrefPrefix="/engagements" />
        ))}
      </div>
      {list.items.length === 0 && (
        <div className="text-sm text-zinc-500">
          No engagements yet. Copy <code>consulting/engagements/_template/</code>{" "}
          to a new <code>&lt;year&gt;-&lt;client&gt;/</code> directory to start one.
        </div>
      )}
    </div>
  );
}
