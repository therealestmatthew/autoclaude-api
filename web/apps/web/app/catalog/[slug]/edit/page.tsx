import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { FrontmatterForm } from "@/components/FrontmatterForm";
import { BodyEditor } from "@/components/BodyEditor";

export const dynamic = "force-dynamic";

export default async function CatalogEdit({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let raw;
  try {
    raw = await api.catalog.raw(slug);
  } catch (e) {
    if (e instanceof Error && e.message.includes("404")) notFound();
    throw e;
  }

  return (
    <article className="space-y-6">
      <header className="space-y-2">
        <div className="text-xs text-zinc-500 font-mono">{raw.path}</div>
        <h1 className="text-2xl font-semibold">Edit catalog/{raw.slug}</h1>
        <div className="flex items-center gap-3 text-xs">
          <Link
            href={`/catalog/${raw.slug}`}
            className="text-brand-700 hover:underline"
          >
            ← view
          </Link>
          <span className="text-zinc-500 font-mono">
            version {raw.version.slice(0, 10)}
          </span>
        </div>
      </header>

      <section className="space-y-2">
        <h2 className="text-xs uppercase tracking-wider text-zinc-500">
          Frontmatter
        </h2>
        <FrontmatterForm raw={raw} />
      </section>

      <section className="space-y-2">
        <h2 className="text-xs uppercase tracking-wider text-zinc-500">Body</h2>
        <BodyEditor
          slug={raw.slug}
          initialBody={raw.body}
          initialVersion={raw.version}
        />
      </section>
    </article>
  );
}
