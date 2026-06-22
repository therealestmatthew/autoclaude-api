import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { MarkdownBody } from "@/components/MarkdownBody";
import type { TimelineEntry } from "@/lib/api-types";


const STATIC_MODE = process.env.NEXT_PUBLIC_STATIC_MODE === "true";

export async function generateStaticParams() {
  return [{ slug: "__unavailable__" }];
}

export const dynamicParams = false;

const COLOR_CLASSES: Record<string, { dot: string; bar: string; text: string }> = {
  emerald: {
    dot: "bg-emerald-500",
    bar: "bg-emerald-100 dark:bg-emerald-900/40 border-emerald-300 dark:border-emerald-800",
    text: "text-emerald-700 dark:text-emerald-300",
  },
  blue: {
    dot: "bg-blue-500",
    bar: "bg-blue-100 dark:bg-blue-900/40 border-blue-300 dark:border-blue-800",
    text: "text-blue-700 dark:text-blue-300",
  },
  amber: {
    dot: "bg-amber-500",
    bar: "bg-amber-100 dark:bg-amber-900/40 border-amber-300 dark:border-amber-800",
    text: "text-amber-700 dark:text-amber-300",
  },
  rose: {
    dot: "bg-rose-500",
    bar: "bg-rose-100 dark:bg-rose-900/40 border-rose-300 dark:border-rose-800",
    text: "text-rose-700 dark:text-rose-300",
  },
  violet: {
    dot: "bg-violet-500",
    bar: "bg-violet-100 dark:bg-violet-900/40 border-violet-300 dark:border-violet-800",
    text: "text-violet-700 dark:text-violet-300",
  },
  zinc: {
    dot: "bg-zinc-500",
    bar: "bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700",
    text: "text-zinc-700 dark:text-zinc-300",
  },
};

const TYPE_LABEL: Record<string, string> = {
  milestone: "Milestone",
  phase: "Phase",
  deliverable: "Deliverable",
  event: "Event",
};

function colorFor(color: string | null | undefined) {
  return COLOR_CLASSES[color ?? "zinc"] ?? COLOR_CLASSES.zinc;
}

function entrySortKey(e: TimelineEntry): string {
  return e.date || e.start || e.end || "9999-12-31";
}

function monthKey(dateStr: string): string {
  return dateStr.slice(0, 7); // YYYY-MM
}

function formatMonth(yyyymm: string): string {
  const [y, m] = yyyymm.split("-");
  const date = new Date(Number(y), Number(m) - 1, 1);
  return date.toLocaleString("en-US", { month: "long", year: "numeric" });
}

function formatDay(dateStr: string): string {
  const [, m, d] = dateStr.split("-");
  return `${Number(m).toString().padStart(2, "0")}/${Number(d).toString().padStart(2, "0")}`;
}

function todayString(): string {
  const t = new Date();
  return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-${String(t.getDate()).padStart(2, "0")}`;
}

function isPast(e: TimelineEntry, today: string): boolean {
  const lastDate = e.end || e.date || e.start;
  return lastDate ? lastDate < today : false;
}

function groupByMonth(entries: TimelineEntry[]): Map<string, TimelineEntry[]> {
  const map = new Map<string, TimelineEntry[]>();
  for (const e of entries) {
    const key = monthKey(entrySortKey(e));
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(e);
  }
  return map;
}

function EntryRow({ entry, today }: { entry: TimelineEntry; today: string }) {
  const colors = colorFor(entry.color);
  const past = isPast(entry, today);
  const isRange = !!(entry.start && entry.end);

  const dateLabel = isRange
    ? `${formatDay(entry.start!)} – ${formatDay(entry.end!)}`
    : formatDay((entry.date || entry.start || entry.end)!);

  return (
    <div
      className={`flex items-start gap-3 py-2.5 ${past ? "opacity-60" : ""}`}
    >
      <div className="w-16 shrink-0 text-xs font-mono text-zinc-500 pt-0.5">
        {dateLabel}
      </div>
      <div className={`w-2 h-2 rounded-full mt-2 shrink-0 ${colors.dot}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className="font-medium text-zinc-900 dark:text-zinc-50">
            {entry.title}
          </span>
          {entry.type && entry.type !== "event" && (
            <span
              className={`text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded ${colors.bar} border ${colors.text}`}
            >
              {TYPE_LABEL[entry.type] ?? entry.type}
            </span>
          )}
          {entry.ref && (
            <Link
              href={`/catalog/${encodeURIComponent(entry.ref)}`}
              className="text-xs text-brand-600 dark:text-brand-400 hover:underline font-mono"
            >
              → {entry.ref}
            </Link>
          )}
        </div>
        {entry.notes && (
          <p className="text-xs text-zinc-500 mt-1">{entry.notes}</p>
        )}
      </div>
    </div>
  );
}

export default async function TimelineDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  if (STATIC_MODE) notFound();
  let timeline;
  try {
    timeline = await api.timelines.get(slug);
  } catch (e) {
    if (e instanceof Error && e.message.includes("404")) notFound();
    throw e;
  }

  const today = todayString();
  const groups = groupByMonth(timeline.entries);
  const sortedMonths = Array.from(groups.keys()).sort();

  const upcomingCount = timeline.entries.filter((e) => !isPast(e, today)).length;
  const pastCount = timeline.entries.length - upcomingCount;

  return (
    <article className="space-y-6 max-w-4xl">
      <nav className="flex items-center gap-2 text-xs text-zinc-500">
        <Link
          href="/timelines"
          className="hover:text-zinc-700 dark:hover:text-zinc-300"
        >
          Timelines
        </Link>
        <span>·</span>
        <code className="font-mono">{timeline.path}</code>
        <span className="ml-auto">
          <Link
            href={`/catalog/${encodeURIComponent(timeline.slug)}/edit`}
            className="rounded border border-zinc-300 dark:border-zinc-700 px-2.5 py-1 text-xs hover:bg-zinc-50 dark:hover:bg-zinc-900"
          >
            Edit
          </Link>
        </span>
      </nav>

      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">
          {timeline.title ?? timeline.slug}
        </h1>
        <p className="text-sm text-zinc-500">
          {timeline.entry_count} {timeline.entry_count === 1 ? "entry" : "entries"}
          {upcomingCount > 0 && (
            <>
              {" · "}
              <span className="text-emerald-600 dark:text-emerald-400">
                {upcomingCount} upcoming
              </span>
            </>
          )}
          {pastCount > 0 && <>{" · "}{pastCount} past</>}
        </p>
        {timeline.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {timeline.tags.map((tag) => (
              <span
                key={tag}
                className="text-xs px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </header>

      {timeline.entries.length === 0 ? (
        <div className="border border-dashed border-zinc-200 dark:border-zinc-800 rounded-lg p-8 text-center text-sm text-zinc-500">
          No entries yet. Add some under{" "}
          <code className="font-mono text-xs">entries:</code> in the file frontmatter.
        </div>
      ) : (
        <div className="space-y-6">
          {sortedMonths.map((monthKey) => (
            <section key={monthKey}>
              <h2 className="sticky top-0 z-10 bg-white dark:bg-zinc-950 text-sm font-semibold text-zinc-700 dark:text-zinc-300 pb-1.5 border-b border-zinc-200 dark:border-zinc-800 mb-1">
                {formatMonth(monthKey)}
              </h2>
              <div className="divide-y divide-zinc-100 dark:divide-zinc-900">
                {groups.get(monthKey)!.map((entry, i) => (
                  <EntryRow
                    key={`${monthKey}-${i}-${entry.title}`}
                    entry={entry}
                    today={today}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {timeline.body && (
        <aside className="border-t border-zinc-200 dark:border-zinc-800 pt-6">
          <h2 className="text-xs uppercase tracking-wider text-zinc-500 font-medium mb-3">
            Notes
          </h2>
          <MarkdownBody source={timeline.body} />
        </aside>
      )}
    </article>
  );
}
