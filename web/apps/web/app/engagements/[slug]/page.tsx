import { api } from "@/lib/api";
import { notFound } from "next/navigation";
import { MarkdownBody } from "@/components/MarkdownBody";
import { Badge } from "@/components/Badge";


const STATIC_MODE = process.env.NEXT_PUBLIC_STATIC_MODE === "true";

export async function generateStaticParams() {
  // Not part of the static export. One placeholder satisfies Next's
  // requirement that this list be non-empty when `output: 'export'` is set.
  return [{ slug: "__unavailable__" }];
}

export const dynamicParams = false;

export default async function EngagementDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  if (STATIC_MODE) notFound();
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
