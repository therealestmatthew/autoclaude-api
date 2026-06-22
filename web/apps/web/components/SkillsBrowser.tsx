"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { SkillCard } from "@/components/SkillCard";
import type { AssetSummary } from "@/lib/api-types";

const SKILL_KINDS = ["agent", "skill", "plugin", "mcp", "prompt"] as const;
type SkillKind = (typeof SKILL_KINDS)[number];

const KIND_LABELS: Record<string, string> = {
  agent: "Agents",
  skill: "Skills",
  plugin: "Plugins",
  mcp: "MCPs",
  prompt: "Prompts",
};

const STATUS_FILTERS = [
  { value: "", label: "All" },
  { value: "adopted", label: "Adopted" },
  { value: "reviewed", label: "Available" },
  { value: "draft", label: "Draft" },
  { value: "archived", label: "Archived" },
] as const;

const DELIVERY_FUNCTIONS = [
  { slug: "discovery",     label: "Discovery & Assessment" },
  { slug: "requirements",  label: "Requirements" },
  { slug: "architecture",  label: "Architecture & Design" },
  { slug: "build",         label: "Build" },
  { slug: "integration",   label: "Integration" },
  { slug: "testing",       label: "Testing & Validation" },
  { slug: "deployment",    label: "Deployment" },
  { slug: "training",      label: "Training & Enablement" },
  { slug: "change-mgmt",   label: "Change Management" },
  { slug: "reporting",     label: "Reporting & PMO" },
] as const;

function adoptionOrder(status: string | null): number {
  switch (status) {
    case "adopted":  return 0;
    case "reviewed": return 1;
    case "draft":    return 2;
    case "archived": return 3;
    default:         return 2;
  }
}

function sortSkills(items: AssetSummary[]): AssetSummary[] {
  return [...items].sort((a, b) => {
    const ao = adoptionOrder(a.status);
    const bo = adoptionOrder(b.status);
    if (ao !== bo) return ao - bo;
    const qa = a.quality ?? 0;
    const qb = b.quality ?? 0;
    if (qa !== qb) return qb - qa;
    return (b.updated_at ?? "").localeCompare(a.updated_at ?? "");
  });
}

function matchesQuery(item: AssetSummary, q: string): boolean {
  const needle = q.toLowerCase();
  if (item.slug.toLowerCase().includes(needle)) return true;
  if (item.title && item.title.toLowerCase().includes(needle)) return true;
  for (const t of item.tags) if (t.toLowerCase().includes(needle)) return true;
  return false;
}

export function SkillsBrowser({ allItems }: { allItems: AssetSummary[] }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const spKind   = searchParams.get("kind")   ?? undefined;
  const spStatus = searchParams.get("status") ?? undefined;
  const spQ      = searchParams.get("q")      ?? undefined;
  const spView   = searchParams.get("view")   ?? undefined;

  const activeKind = SKILL_KINDS.includes(spKind as SkillKind) ? (spKind as SkillKind) : undefined;
  const view = spView === "function" ? "function" : "kind";

  function buildHref(params: { kind?: string; status?: string; q?: string; view?: string }): string {
    const usp = new URLSearchParams();
    if (params.kind)   usp.set("kind",   params.kind);
    if (params.status) usp.set("status", params.status);
    if (params.q)      usp.set("q",      params.q);
    if (params.view)   usp.set("view",   params.view);
    const s = usp.toString();
    return `/skills${s ? `?${s}` : ""}`;
  }

  // Restrict the dataset to skill-shaped kinds, then apply URL filters.
  const filtered = useMemo(() => {
    let items = allItems.filter(
      (i) => i.kind && (SKILL_KINDS as readonly string[]).includes(i.kind),
    );
    if (activeKind) items = items.filter((i) => i.kind === activeKind);
    if (spStatus)   items = items.filter((i) => i.status === spStatus);
    if (spQ)        items = items.filter((i) => matchesQuery(i, spQ));
    return sortSkills(items);
  }, [allItems, activeKind, spStatus, spQ]);

  const adoptedCount   = filtered.filter((i) => i.status === "adopted").length;
  const availableCount = filtered.filter((i) => i.status === "reviewed").length;
  const draftCount     = filtered.filter((i) => i.status === "draft").length;

  // By-function grouping.
  const { byFunction, untagged } = useMemo(() => {
    const m = new Map<string, AssetSummary[]>();
    const u: AssetSummary[] = [];
    for (const item of filtered) {
      const fns = item.delivery_functions ?? [];
      if (fns.length === 0) {
        u.push(item);
      } else {
        for (const fn of fns) {
          if (!m.has(fn)) m.set(fn, []);
          m.get(fn)!.push(item);
        }
      }
    }
    return { byFunction: m, untagged: u };
  }, [filtered]);

  function onSearchSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const q = (fd.get("q") as string | null) ?? "";
    router.push(buildHref({ kind: spKind, status: spStatus, view: spView, q: q || undefined }));
  }

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold">Skills & Tools</h1>
          <p className="text-sm text-zinc-500 mt-1">
            {filtered.length} tools ·{" "}
            <span className="text-emerald-600 dark:text-emerald-400 font-medium" title="Installed and in active use">
              {adoptedCount} adopted
            </span>
            {" · "}
            <span className="text-blue-600 dark:text-blue-400" title="Vetted, not yet installed">
              {availableCount} available
            </span>
            {draftCount > 0 && (
              <>
                {" · "}
                <span className="text-amber-600 dark:text-amber-400">{draftCount} draft</span>
              </>
            )}
          </p>
        </div>
        <form onSubmit={onSearchSubmit} className="flex items-center gap-2">
          <input
            type="text"
            name="q"
            placeholder="search title, slug, tags…"
            defaultValue={spQ ?? ""}
            className="px-3 py-1.5 text-sm border border-zinc-200 dark:border-zinc-800 rounded-md bg-white dark:bg-zinc-950 w-56"
          />
        </form>
      </header>

      <div className="flex items-center gap-1 text-xs">
        <span className="text-zinc-400 mr-1">View:</span>
        <ViewTab label="By Kind"     href={buildHref({ kind: spKind, status: spStatus, q: spQ })}                    active={view === "kind"} />
        <ViewTab label="By Function" href={buildHref({ kind: spKind, status: spStatus, q: spQ, view: "function" })} active={view === "function"} />
      </div>

      {view === "kind" && (
        <>
          <div className="flex flex-wrap gap-2 text-xs border-b border-zinc-200 dark:border-zinc-800 pb-3">
            <KindTab label="All" href={buildHref({ status: spStatus, q: spQ })} active={!activeKind} />
            {SKILL_KINDS.map((k) => (
              <KindTab
                key={k}
                label={KIND_LABELS[k]}
                href={buildHref({ kind: k, status: spStatus, q: spQ })}
                active={activeKind === k}
              />
            ))}
          </div>

          <div className="flex flex-wrap gap-2 text-xs">
            {STATUS_FILTERS.map(({ value, label }) => (
              <StatusTab
                key={value}
                label={label}
                href={buildHref({ kind: spKind, status: value || undefined, q: spQ })}
                active={(spStatus ?? "") === value}
              />
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {filtered.map((a) => <SkillCard key={a.path} asset={a} />)}
          </div>
          {filtered.length === 0 && (
            <div className="text-sm text-zinc-500 py-8 text-center">
              No tools match. <Link href="/skills" className="underline">Clear filters</Link>
            </div>
          )}
        </>
      )}

      {view === "function" && (
        <>
          <div className="flex flex-wrap gap-2 text-xs">
            {STATUS_FILTERS.map(({ value, label }) => (
              <StatusTab
                key={value}
                label={label}
                href={buildHref({ status: value || undefined, q: spQ, view: "function" })}
                active={(spStatus ?? "") === value}
              />
            ))}
          </div>

          {filtered.length === 0 && (
            <div className="text-sm text-zinc-500 py-8 text-center">
              No tools match. <Link href="/skills?view=function" className="underline">Clear filters</Link>
            </div>
          )}

          <div className="space-y-10">
            {DELIVERY_FUNCTIONS.map(({ slug, label }) => {
              const section = byFunction.get(slug);
              if (!section || section.length === 0) return null;
              return (
                <section key={slug}>
                  <div className="flex items-center gap-3 mb-4">
                    <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">{label}</h2>
                    <span className="text-xs text-zinc-400">{section.length} tool{section.length !== 1 ? "s" : ""}</span>
                    <div className="flex-1 border-t border-zinc-100 dark:border-zinc-800" />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {section.map((a) => <SkillCard key={`${slug}:${a.path}`} asset={a} />)}
                  </div>
                </section>
              );
            })}

            {untagged.length > 0 && (
              <section>
                <div className="flex items-center gap-3 mb-4">
                  <h2 className="text-base font-semibold text-zinc-500 dark:text-zinc-400">General / Untagged</h2>
                  <span className="text-xs text-zinc-400">{untagged.length} tool{untagged.length !== 1 ? "s" : ""}</span>
                  <div className="flex-1 border-t border-zinc-100 dark:border-zinc-800" />
                </div>
                <p className="text-xs text-zinc-400 mb-3">
                  These tools don&apos;t have a <code className="font-mono">delivery_function</code> tag yet.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {untagged.map((a) => <SkillCard key={a.path} asset={a} />)}
                </div>
              </section>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function ViewTab({ label, href, active }: { label: string; href: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={`px-3 py-1 rounded-md border text-xs font-medium transition-colors ${
        active
          ? "border-zinc-900 dark:border-zinc-100 bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900"
          : "border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400 hover:border-zinc-400"
      }`}
    >
      {label}
    </Link>
  );
}

function KindTab({ label, href, active }: { label: string; href: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={`px-3 py-1.5 rounded-md font-medium ${
        active
          ? "bg-brand-500 text-white"
          : "text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"
      }`}
    >
      {label}
    </Link>
  );
}

function StatusTab({ label, href, active }: { label: string; href: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={`px-2.5 py-1 rounded-md border ${
        active
          ? "border-brand-500 bg-brand-50 dark:bg-zinc-800 text-brand-700 dark:text-zinc-100"
          : "border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 hover:border-zinc-400"
      }`}
    >
      {label}
    </Link>
  );
}
