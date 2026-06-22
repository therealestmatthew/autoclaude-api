import Link from "next/link";
import { api } from "@/lib/api";
import { ApiBanner } from "@/components/ApiBanner";
import { Badge } from "@/components/Badge";
import type { AssetSummary, TimelineSummary } from "@/lib/api-types";


const SKILL_KINDS = ["agent", "skill", "plugin", "mcp", "prompt"] as const;
type SkillKind = (typeof SKILL_KINDS)[number];

const KIND_LABELS: Record<SkillKind, string> = {
  agent: "Agents",
  skill: "Skills",
  plugin: "Plugins",
  mcp: "MCPs",
  prompt: "Prompts",
};

const KIND_ICONS: Record<SkillKind, string> = {
  agent: "🤖",
  skill: "⚡",
  plugin: "🔌",
  mcp: "🔧",
  prompt: "💬",
};

const KIND_HINTS: Record<SkillKind, string> = {
  agent: "autonomous workers",
  skill: "reusable how-tos",
  plugin: "bundled installs",
  mcp: "external servers",
  prompt: "canned starters",
};

function todayString(): string {
  const t = new Date();
  return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-${String(t.getDate()).padStart(2, "0")}`;
}

export default async function DashboardPage() {
  let stats;
  let allAdopted;
  let allReviewed;
  let timelines;
  try {
    [stats, allAdopted, allReviewed, timelines] = await Promise.all([
      api.stats(),
      api.catalog.list({ status: "adopted", limit: 500 }),
      api.catalog.list({ status: "reviewed", limit: 500 }),
      api.timelines.list(),
    ]);
  } catch {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <ApiBanner />
      </div>
    );
  }

  const adoptedByKind: Record<SkillKind, number> = {
    agent: 0,
    skill: 0,
    plugin: 0,
    mcp: 0,
    prompt: 0,
  };
  const availableByKind: Record<SkillKind, number> = {
    agent: 0,
    skill: 0,
    plugin: 0,
    mcp: 0,
    prompt: 0,
  };
  for (const item of allAdopted.items) {
    if (item.kind && SKILL_KINDS.includes(item.kind as SkillKind)) {
      adoptedByKind[item.kind as SkillKind]++;
    }
  }
  for (const item of allReviewed.items) {
    if (item.kind && SKILL_KINDS.includes(item.kind as SkillKind)) {
      availableByKind[item.kind as SkillKind]++;
    }
  }

  const recentAdopted = [...allAdopted.items]
    .filter((i) => i.kind && SKILL_KINDS.includes(i.kind as SkillKind))
    .sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""))
    .slice(0, 5);

  const today = todayString();
  const activeTimelines = timelines.items.filter(
    (t) => !t.last_date || t.last_date >= today
  );

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Welcome to Forge. Your AI toolkit is below.
        </p>
      </header>

      {/* Your toolkit — adopted by kind */}
      <section>
        <div className="flex items-baseline justify-between mb-3">
          <h2 className="text-sm uppercase tracking-wider text-zinc-500">
            Your toolkit
          </h2>
          <Link
            href="/skills?status=adopted"
            className="text-sm text-brand-700 dark:text-brand-100 hover:underline"
          >
            View all →
          </Link>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {SKILL_KINDS.map((k) => (
            <Link
              key={k}
              href={`/skills?kind=${k}&status=adopted`}
              className="block p-4 border border-zinc-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-950 hover:border-brand-500 transition-colors"
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-2xl">{KIND_ICONS[k]}</span>
                <span className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
                  {adoptedByKind[k]}
                </span>
              </div>
              <div className="mt-2 text-sm font-medium text-zinc-900 dark:text-zinc-50">
                {KIND_LABELS[k]}
              </div>
              <div className="text-xs text-zinc-500">{KIND_HINTS[k]}</div>
              {availableByKind[k] > 0 && (
                <div className="text-xs text-blue-600 dark:text-blue-400 mt-1.5">
                  +{availableByKind[k]} available
                </div>
              )}
            </Link>
          ))}
        </div>
      </section>

      {/* Recently adopted */}
      {recentAdopted.length > 0 && (
        <section>
          <h2 className="text-sm uppercase tracking-wider text-zinc-500 mb-3">
            Recently adopted
          </h2>
          <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg overflow-hidden divide-y divide-zinc-100 dark:divide-zinc-900">
            {recentAdopted.map((a) => (
              <Link
                key={a.path}
                href={`/skills/${encodeURIComponent(a.slug)}`}
                className="flex items-center gap-3 px-4 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-900"
              >
                <span className="text-lg">
                  {KIND_ICONS[a.kind as SkillKind] ?? "📦"}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-zinc-900 dark:text-zinc-50 truncate">
                    {a.title ?? a.slug}
                  </div>
                  <div className="text-xs text-zinc-500 truncate">{a.slug}</div>
                </div>
                {a.kind && <Badge variant="kind">{a.kind}</Badge>}
                {a.updated_at && (
                  <span className="text-xs text-zinc-500 font-mono shrink-0">
                    {a.updated_at}
                  </span>
                )}
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Active timelines */}
      {activeTimelines.length > 0 && (
        <section>
          <div className="flex items-baseline justify-between mb-3">
            <h2 className="text-sm uppercase tracking-wider text-zinc-500">
              Active timelines
            </h2>
            <Link
              href="/timelines"
              className="text-sm text-brand-700 dark:text-brand-100 hover:underline"
            >
              View all →
            </Link>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {activeTimelines.slice(0, 6).map((t: TimelineSummary) => (
              <Link
                key={t.path}
                href={`/timelines/${encodeURIComponent(t.slug)}`}
                className="block p-3 border border-zinc-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-950 hover:border-brand-500 transition-colors"
              >
                <div className="font-medium text-zinc-900 dark:text-zinc-50 truncate text-sm">
                  {t.title ?? t.slug}
                </div>
                <div className="text-xs text-zinc-500 mt-1">
                  {t.entry_count} {t.entry_count === 1 ? "entry" : "entries"}
                  {t.first_date && t.last_date && t.first_date !== t.last_date && (
                    <> · {t.first_date} → {t.last_date}</>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Library at a glance — operator concerns, smaller */}
      <section>
        <h2 className="text-sm uppercase tracking-wider text-zinc-500 mb-3">
          Library
        </h2>
        <div className="flex flex-wrap gap-2 text-sm">
          <LibraryPill href="/catalog" label="All catalog items" count={stats.stats.by_bucket.catalog ?? 0} />
          <LibraryPill href="/queue" label="Pending review" count={stats.stats.by_bucket.queue ?? 0} />
          <LibraryPill href="/proposals" label="Proposals" count={undefined} />
          <LibraryPill href="/engagements" label="Engagements" count={stats.stats.by_bucket.engagement ?? 0} />
          <LibraryPill href="/plans" label="Plans" count={stats.stats.by_bucket.plan ?? 0} />
          {stats.stats.with_issues > 0 && (
            <LibraryPill
              href="/catalog"
              label="With issues"
              count={stats.stats.with_issues}
              variant="warn"
            />
          )}
        </div>
      </section>
    </div>
  );
}

function LibraryPill({
  href,
  label,
  count,
  variant,
}: {
  href: string;
  label: string;
  count: number | undefined;
  variant?: "warn";
}) {
  const cls =
    variant === "warn"
      ? "border-rose-200 dark:border-rose-900 bg-rose-50 dark:bg-rose-950/30 text-rose-700 dark:text-rose-300"
      : "border-zinc-200 dark:border-zinc-800 hover:border-zinc-400 text-zinc-700 dark:text-zinc-300";
  return (
    <Link
      href={href}
      className={`flex items-center gap-2 px-3 py-1.5 border rounded-md ${cls}`}
    >
      <span>{label}</span>
      {count !== undefined && (
        <span className="font-mono text-xs text-zinc-500">{count}</span>
      )}
    </Link>
  );
}
