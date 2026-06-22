import Link from "next/link";
import { api } from "@/lib/api";
import { ApiBanner } from "@/components/ApiBanner";


export default async function TimelinesPage() {
  let list;
  try {
    list = await api.timelines.list();
  } catch {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Timelines</h1>
        <ApiBanner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold">Timelines</h1>
          <p className="text-sm text-zinc-500 mt-1">
            {list.total} timeline{list.total === 1 ? "" : "s"}. Date-shaped views for
            project plans, adoption roadmaps, content calendars — anything that benefits
            from a temporal lens.
          </p>
        </div>
      </header>

      {list.items.length === 0 ? (
        <div className="border border-dashed border-zinc-200 dark:border-zinc-800 rounded-lg p-8 text-center text-sm text-zinc-500">
          <p>No timelines yet.</p>
          <p className="mt-2">
            Create one by copying{" "}
            <code className="font-mono text-xs">/timelines/_template.md</code> to{" "}
            <code className="font-mono text-xs">/timelines/&lt;your-slug&gt;.md</code>.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {list.items.map((t) => (
            <Link
              key={t.path}
              href={`/timelines/${encodeURIComponent(t.slug)}`}
              className="block p-4 border border-zinc-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-950 hover:border-brand-500 transition-colors"
            >
              <div className="flex items-baseline justify-between gap-2">
                <h3 className="font-medium text-zinc-900 dark:text-zinc-50 truncate">
                  {t.title ?? t.slug}
                </h3>
                <span className="text-xs text-zinc-500 shrink-0">
                  {t.entry_count} {t.entry_count === 1 ? "entry" : "entries"}
                </span>
              </div>
              <div className="text-xs text-zinc-400 mt-0.5 truncate font-mono">{t.slug}</div>
              {(t.first_date || t.last_date) && (
                <div className="text-xs text-zinc-500 mt-2">
                  {t.first_date}
                  {t.last_date && t.last_date !== t.first_date && ` → ${t.last_date}`}
                </div>
              )}
              {t.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-3">
                  {t.tags.slice(0, 4).map((tag) => (
                    <span
                      key={tag}
                      className="text-xs px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
