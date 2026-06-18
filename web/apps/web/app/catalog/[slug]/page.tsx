import Link from "next/link";
import { api } from "@/lib/api";
import { notFound } from "next/navigation";
import { MarkdownBody } from "@/components/MarkdownBody";
import { Badge } from "@/components/Badge";

export const dynamic = "force-dynamic";

export default async function CatalogDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let asset;
  try {
    asset = await api.catalog.get(slug);
  } catch (e) {
    if (e instanceof Error && e.message.includes("404")) notFound();
    throw e;
  }
  return (
    <article className="space-y-6">
      <header>
        <div className="flex items-center justify-between gap-2 text-xs text-zinc-500 mb-2">
          <div className="flex items-center gap-2">
            <span>catalog</span> <span>·</span>
            <code className="font-mono">{asset.path}</code>
          </div>
          <Link
            href={`/catalog/${asset.slug}/edit`}
            className="rounded border border-zinc-300 dark:border-zinc-700 px-2.5 py-1 text-xs hover:bg-zinc-50 dark:hover:bg-zinc-900"
          >
            Edit
          </Link>
        </div>
        <h1 className="text-2xl font-semibold">{asset.title ?? asset.slug}</h1>
        <div className="flex flex-wrap items-center gap-2 mt-2">
          {asset.kind && <Badge variant="kind">{asset.kind}</Badge>}
          {asset.status && <Badge variant="status">{asset.status}</Badge>}
          {asset.tags.map((t) => (
            <Badge key={t} variant="tag">
              {t}
            </Badge>
          ))}
        </div>
      </header>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
        <div>
          <h2 className="text-xs uppercase tracking-wider text-zinc-500 mb-1">
            Source
          </h2>
          <pre className="text-xs bg-zinc-50 dark:bg-zinc-900 p-3 rounded overflow-x-auto">
            {JSON.stringify(asset.source ?? {}, null, 2)}
          </pre>
        </div>
        <div>
          <h2 className="text-xs uppercase tracking-wider text-zinc-500 mb-1">
            Discovered
          </h2>
          <pre className="text-xs bg-zinc-50 dark:bg-zinc-900 p-3 rounded overflow-x-auto">
            {JSON.stringify(asset.discovered ?? {}, null, 2)}
          </pre>
        </div>
      </section>

      <section>
        <h2 className="text-xs uppercase tracking-wider text-zinc-500 mb-2">
          Body
        </h2>
        <MarkdownBody source={asset.body} />
      </section>
    </article>
  );
}
