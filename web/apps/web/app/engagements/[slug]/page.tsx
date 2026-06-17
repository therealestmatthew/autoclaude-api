import { api } from "@/lib/api";
import { notFound } from "next/navigation";
import { MarkdownBody } from "@/components/MarkdownBody";
import { Badge } from "@/components/Badge";

export const dynamic = "force-dynamic";

export default async function EngagementDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let asset;
  try {
    asset = await api.engagements.get(slug);
  } catch (e) {
    if (e instanceof Error && e.message.includes("404")) notFound();
    throw e;
  }
  return (
    <article className="space-y-6">
      <header>
        <div className="text-xs text-zinc-500 mb-2 font-mono">{asset.path}</div>
        <h1 className="text-2xl font-semibold">{asset.title ?? asset.slug}</h1>
        <div className="flex flex-wrap items-center gap-2 mt-2">
          {asset.status && <Badge variant="status">{asset.status}</Badge>}
        </div>
      </header>
      <MarkdownBody source={asset.body} />
    </article>
  );
}
