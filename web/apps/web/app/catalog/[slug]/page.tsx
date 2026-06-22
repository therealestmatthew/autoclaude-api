import Link from "next/link";
import { api } from "@/lib/api";
import { notFound } from "next/navigation";
import { MarkdownBody } from "@/components/MarkdownBody";
import { Badge } from "@/components/Badge";
import type { AssetSummary } from "@/lib/api-types";

const STATIC_MODE = process.env.NEXT_PUBLIC_STATIC_MODE === "true";

export async function generateStaticParams() {
  if (!STATIC_MODE) return [];
  const { staticData } = await import("@/lib/static-data");
  const all = await staticData.allSlugs(["catalog"]);
  return all.map((a) => ({ slug: a.slug }));
}

const SKILL_KINDS = new Set(["agent", "skill", "plugin", "mcp", "prompt"]);

function statusBadgeColors(status: string | null) {
  switch (status) {
    case "adopted":
      return "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300";
    case "reviewed":
      return "bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300";
    case "archived":
      return "bg-zinc-100 dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 text-zinc-500";
    default:
      return "bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300";
  }
}

function StatusLine({ status }: { status: string | null }) {
  const text =
    status === "adopted"
      ? "Adopted — actively in use"
      : status === "reviewed"
      ? "Available — reviewed, not yet adopted"
      : status === "archived"
      ? "Archived — no longer recommended"
      : "Draft — awaiting review";
  return (
    <div
      className={`flex items-center gap-2 px-3 py-2 rounded-md border text-sm ${statusBadgeColors(status)}`}
    >
      <span className="font-medium">{text}</span>
    </div>
  );
}

function detailHrefFor(kind: string | null | undefined, slug: string): string {
  if (kind && SKILL_KINDS.has(kind)) {
    return `/skills/${encodeURIComponent(slug)}`;
  }
  return `/catalog/${encodeURIComponent(slug)}`;
}

function Relations({ relations }: { relations: Record<string, unknown> | null }) {
  if (!relations) return null;
  const parent = relations.parent as string | undefined;
  const related = (relations.related as string[] | undefined) ?? [];
  const supersedes = (relations.supersedes as string[] | undefined) ?? [];
  if (!parent && related.length === 0 && supersedes.length === 0) return null;

  return (
    <div className="space-y-2">
      <h2 className="text-xs uppercase tracking-wider text-zinc-500 font-medium">
        Related
      </h2>
      <div className="space-y-1.5 text-sm">
        {parent && (
          <div className="flex items-center gap-2">
            <span className="text-zinc-400 text-xs w-20 shrink-0">parent</span>
            <Link
              href={`/catalog/${encodeURIComponent(parent)}`}
              className="text-brand-600 dark:text-brand-400 hover:underline font-mono text-xs"
            >
              {parent}
            </Link>
          </div>
        )}
        {related.map((slug) => (
          <div key={slug} className="flex items-center gap-2">
            <span className="text-zinc-400 text-xs w-20 shrink-0">related</span>
            <Link
              href={`/catalog/${encodeURIComponent(slug)}`}
              className="text-brand-600 dark:text-brand-400 hover:underline font-mono text-xs"
            >
              {slug}
            </Link>
          </div>
        ))}
        {supersedes.map((slug) => (
          <div key={slug} className="flex items-center gap-2">
            <span className="text-zinc-400 text-xs w-20 shrink-0">
              supersedes
            </span>
            <Link
              href={`/catalog/${encodeURIComponent(slug)}`}
              className="text-zinc-500 hover:underline font-mono text-xs line-through"
            >
              {slug}
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}

function Source({
  source,
  discovered,
}: {
  source: Record<string, unknown> | null;
  discovered: Record<string, unknown> | null;
}) {
  const url = source?.url as string | undefined;
  const license = source?.license as string | undefined;
  const sourceType = source?.type as string | undefined;
  const via = discovered?.via as string | undefined;
  const on = discovered?.on as string | undefined;

  if (!url && !license && !via && !sourceType) return null;

  return (
    <div className="space-y-2">
      <h2 className="text-xs uppercase tracking-wider text-zinc-500 font-medium">
        Provenance
      </h2>
      <div className="space-y-1.5 text-xs text-zinc-500">
        {url && (
          <div>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-brand-600 dark:text-brand-400 hover:underline break-all"
            >
              {url}
            </a>
          </div>
        )}
        {sourceType && (
          <div>
            Source type: <span className="font-mono">{sourceType}</span>
          </div>
        )}
        {license && (
          <div>
            License: <span className="font-mono">{license}</span>
          </div>
        )}
        {via && (
          <div>
            Discovered via {via}
            {on ? ` · ${on}` : ""}
          </div>
        )}
      </div>
    </div>
  );
}

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

  // For repo/org-kind assets, surface child catalog entries that match the
  // slug. The list endpoint doesn't expose relations.parent on summaries, so
  // we use the search endpoint as a proxy and filter to skill-shaped kinds.
  let children: AssetSummary[] = [];
  if (asset.kind === "repo" || asset.kind === "org") {
    try {
      const searchHits = await api.search({ q: slug, bucket: "catalog", limit: 200 });
      children = searchHits.hits.filter(
        (h) =>
          h.slug !== slug &&
          (h.kind === "agent" ||
            h.kind === "skill" ||
            h.kind === "plugin" ||
            h.kind === "mcp" ||
            h.kind === "prompt")
      );
    } catch {
      children = [];
    }
  }

  return (
    <article className="space-y-6 max-w-4xl">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-xs text-zinc-500">
        <Link
          href="/catalog"
          className="hover:text-zinc-700 dark:hover:text-zinc-300"
        >
          Catalog
        </Link>
        <span>·</span>
        <code className="font-mono">{asset.path}</code>
        <span className="ml-auto flex items-center gap-2">
          <a
            href={`/data/raw/${encodeURIComponent(asset.slug)}.md`}
            download={`${asset.slug}.md`}
            className="rounded border border-zinc-300 dark:border-zinc-700 px-2.5 py-1 text-xs hover:bg-zinc-50 dark:hover:bg-zinc-900"
          >
            ⬇ Download .md
          </a>
          {!STATIC_MODE && (
            <Link
              href={`/catalog/${encodeURIComponent(asset.slug)}/edit`}
              className="rounded border border-zinc-300 dark:border-zinc-700 px-2.5 py-1 text-xs hover:bg-zinc-50 dark:hover:bg-zinc-900"
            >
              Edit
            </Link>
          )}
        </span>
      </nav>

      {/* Title block */}
      <header className="space-y-3">
        <h1 className="text-2xl font-semibold">{asset.title ?? asset.slug}</h1>
        <div className="flex flex-wrap items-center gap-2">
          {asset.kind && <Badge variant="kind">{asset.kind}</Badge>}
          {asset.quality != null && asset.quality > 0 && (
            <span className="text-sm text-amber-500 font-medium">
              {"★".repeat(asset.quality)}
            </span>
          )}
          {asset.tags.map((t) => (
            <Badge key={t} variant="tag">
              {t}
            </Badge>
          ))}
        </div>
      </header>

      <StatusLine status={asset.status} />

      {/* Body — primary content */}
      <section>
        {asset.body ? (
          <MarkdownBody source={asset.body} />
        ) : (
          <div className="border border-dashed border-zinc-200 dark:border-zinc-800 rounded-lg p-4 text-sm text-zinc-500">
            No documentation yet.
            {asset.source &&
              typeof (asset.source as { url?: unknown }).url === "string" && (
                <>
                  {" "}
                  <a
                    href={(asset.source as { url: string }).url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-brand-600 dark:text-brand-400 hover:underline"
                  >
                    View original source →
                  </a>
                </>
              )}
          </div>
        )}
      </section>

      {/* Children — for repo/org parents */}
      {children.length > 0 && (
        <section className="border-t border-zinc-200 dark:border-zinc-800 pt-6">
          <h2 className="text-xs uppercase tracking-wider text-zinc-500 font-medium mb-3">
            Extracted from this {asset.kind}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {children.slice(0, 12).map((child) => (
              <Link
                key={child.path}
                href={detailHrefFor(child.kind, child.slug)}
                className="block p-3 border border-zinc-200 dark:border-zinc-800 rounded-md hover:border-brand-500 transition-colors"
              >
                <div className="flex items-center gap-2 mb-1">
                  {child.kind && <Badge variant="kind">{child.kind}</Badge>}
                  {child.status === "adopted" && (
                    <span className="text-xs text-emerald-600 dark:text-emerald-400">
                      ✓ adopted
                    </span>
                  )}
                </div>
                <div className="text-sm font-medium truncate">
                  {child.title ?? child.slug}
                </div>
              </Link>
            ))}
          </div>
          {children.length > 12 && (
            <p className="text-xs text-zinc-500 mt-2">
              Showing 12 of {children.length}.{" "}
              <Link
                href={`/catalog?q=${encodeURIComponent(slug)}`}
                className="underline"
              >
                See all matches
              </Link>
            </p>
          )}
        </section>
      )}

      {/* Footer aside: relations + provenance */}
      <aside className="border-t border-zinc-200 dark:border-zinc-800 pt-6 space-y-6">
        <Relations relations={asset.relations} />
        <Source source={asset.source} discovered={asset.discovered} />
        {asset.issues.length > 0 && (
          <div className="space-y-2">
            <h2 className="text-xs uppercase tracking-wider text-zinc-500 font-medium">
              Issues
            </h2>
            <div className="flex flex-wrap gap-1">
              {asset.issues.map((i) => (
                <Badge key={i} variant="issue">
                  {i}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </aside>
    </article>
  );
}
