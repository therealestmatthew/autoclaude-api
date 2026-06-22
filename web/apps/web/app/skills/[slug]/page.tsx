import Link from "next/link";
import { api } from "@/lib/api";
import { notFound } from "next/navigation";
import { MarkdownBody } from "@/components/MarkdownBody";
import { Badge } from "@/components/Badge";

const STATIC_MODE = process.env.NEXT_PUBLIC_STATIC_MODE === "true";

export async function generateStaticParams() {
  if (!STATIC_MODE) return [];
  const { staticData } = await import("@/lib/static-data");
  const all = await staticData.allSlugs(["catalog"]);
  const skillKinds = new Set(["agent", "skill", "plugin", "mcp", "prompt"]);
  return all
    .filter((a) => a.kind && skillKinds.has(a.kind))
    .map((a) => ({ slug: a.slug }));
}

const KIND_ICON: Record<string, string> = {
  agent: "🤖",
  skill: "⚡",
  plugin: "🔌",
  mcp: "🔧",
  prompt: "💬",
};

function AdoptionBanner({ status }: { status: string | null }) {
  const s = status ?? "draft";
  if (s === "adopted") {
    return (
      <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-sm">
        <span className="text-emerald-600 dark:text-emerald-400 font-semibold">✓ Adopted</span>
        <span className="text-emerald-700 dark:text-emerald-300">
          Active in your Claude toolkit — find it in <code className="font-mono text-xs">/claude/</code>
        </span>
      </div>
    );
  }
  if (s === "reviewed") {
    return (
      <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 text-sm">
        <span className="text-blue-600 dark:text-blue-400 font-semibold">● Available</span>
        <span className="text-blue-700 dark:text-blue-300">
          Reviewed and approved — not yet adopted into the active toolkit
        </span>
      </div>
    );
  }
  if (s === "archived") {
    return (
      <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-zinc-100 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 text-sm">
        <span className="text-zinc-500 font-semibold">✕ Archived</span>
        <span className="text-zinc-500">No longer recommended for active use</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-sm">
      <span className="text-amber-600 dark:text-amber-400 font-semibold">◌ Draft</span>
      <span className="text-amber-700 dark:text-amber-300">
        Awaiting review — not yet vetted for production use
      </span>
    </div>
  );
}

function RelationsPanel({ relations }: { relations: Record<string, unknown> | null }) {
  if (!relations) return null;
  const parent = relations.parent as string | undefined;
  const related = (relations.related as string[] | undefined) ?? [];
  const supersedes = (relations.supersedes as string[] | undefined) ?? [];
  if (!parent && related.length === 0 && supersedes.length === 0) return null;

  return (
    <div className="space-y-2">
      <h2 className="text-xs uppercase tracking-wider text-zinc-500 font-medium">Related</h2>
      <div className="space-y-1.5 text-sm">
        {parent && (
          <div className="flex items-center gap-2">
            <span className="text-zinc-400 text-xs w-20 shrink-0">parent repo</span>
            <Link href={`/catalog/${encodeURIComponent(parent)}`} className="text-brand-600 dark:text-brand-400 hover:underline font-mono text-xs">
              {parent}
            </Link>
          </div>
        )}
        {related.map((slug) => (
          <div key={slug} className="flex items-center gap-2">
            <span className="text-zinc-400 text-xs w-20 shrink-0">related</span>
            <Link href={`/skills/${encodeURIComponent(slug)}`} className="text-brand-600 dark:text-brand-400 hover:underline font-mono text-xs">
              {slug}
            </Link>
          </div>
        ))}
        {supersedes.map((slug) => (
          <div key={slug} className="flex items-center gap-2">
            <span className="text-zinc-400 text-xs w-20 shrink-0">supersedes</span>
            <Link href={`/skills/${encodeURIComponent(slug)}`} className="text-zinc-500 hover:underline font-mono text-xs line-through">
              {slug}
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}

function SourcePanel({ source, discovered }: { source: Record<string, unknown> | null; discovered: Record<string, unknown> | null }) {
  const url = source?.url as string | undefined;
  const license = source?.license as string | undefined;
  const via = discovered?.via as string | undefined;
  const on = discovered?.on as string | undefined;

  if (!url && !license && !via) return null;

  return (
    <div className="space-y-2">
      <h2 className="text-xs uppercase tracking-wider text-zinc-500 font-medium">Provenance</h2>
      <div className="space-y-1.5 text-xs text-zinc-500">
        {url && (
          <div>
            <a href={url} target="_blank" rel="noopener noreferrer" className="text-brand-600 dark:text-brand-400 hover:underline break-all">
              {url}
            </a>
          </div>
        )}
        {license && <div>License: <span className="font-mono">{license}</span></div>}
        {via && <div>Discovered via {via}{on ? ` · ${on}` : ""}</div>}
      </div>
    </div>
  );
}

export default async function SkillDetail({
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

  const icon = KIND_ICON[asset.kind ?? ""] ?? "📦";

  return (
    <article className="space-y-6 max-w-4xl">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-xs text-zinc-500">
        <Link href="/skills" className="hover:text-zinc-700 dark:hover:text-zinc-300">Skills & Tools</Link>
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

      {/* Title */}
      <header className="space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{icon}</span>
          <h1 className="text-2xl font-semibold">{asset.title ?? asset.slug}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {asset.kind && <Badge variant="kind">{asset.kind}</Badge>}
          {asset.quality !== null && (
            <span className="text-sm text-amber-500 font-medium">{"★".repeat(asset.quality)}</span>
          )}
          {asset.tags.map((t) => (
            <Badge key={t} variant="tag">{t}</Badge>
          ))}
        </div>
      </header>

      {/* Adoption status */}
      <AdoptionBanner status={asset.status} />

      {/* Main content — the usage guide */}
      <section>
        {asset.body ? (
          <MarkdownBody source={asset.body} />
        ) : (
          <p className="text-sm text-zinc-500 italic">No documentation yet.</p>
        )}
      </section>

      {/* Sidebar: relations + source */}
      <aside className="border-t border-zinc-200 dark:border-zinc-800 pt-6 space-y-6">
        <RelationsPanel relations={asset.relations} />
        <SourcePanel source={asset.source} discovered={asset.discovered} />
        {asset.issues.length > 0 && (
          <div className="space-y-2">
            <h2 className="text-xs uppercase tracking-wider text-zinc-500 font-medium">Issues</h2>
            <div className="flex flex-wrap gap-1">
              {asset.issues.map((i) => <Badge key={i} variant="issue">{i}</Badge>)}
            </div>
          </div>
        )}
      </aside>
    </article>
  );
}
