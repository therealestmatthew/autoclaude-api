import { api } from "@/lib/api";
import { notFound } from "next/navigation";
import { MarkdownBody } from "@/components/MarkdownBody";
import { Badge } from "@/components/Badge";

export const dynamic = "force-dynamic";

export default async function QueueDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let asset;
  try {
    asset = await api.queue.get(slug);
  } catch (e) {
    if (e instanceof Error && e.message.includes("404")) notFound();
    throw e;
  }
  const sourceUrl =
    typeof asset.source?.url === "string" ? (asset.source.url as string) : null;
  return (
    <article className="space-y-6">
      <header>
        <div className="text-xs text-zinc-500 mb-2 font-mono">{asset.path}</div>
        <h1 className="text-2xl font-semibold">{asset.title ?? asset.slug}</h1>
        <div className="flex flex-wrap items-center gap-2 mt-2">
          {asset.kind && <Badge variant="kind">{asset.kind}</Badge>}
          <Badge variant="status">draft</Badge>
          {sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-brand-700 hover:underline"
            >
              ↗ source
            </a>
          )}
        </div>
      </header>
      <MarkdownBody source={asset.body} />
    </article>
  );
}
