"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { AssetCard } from "@/components/AssetCard";
import type { AssetSummary } from "@/lib/api-types";

const KINDS = ["agent", "skill", "plugin", "mcp", "prompt", "repo", "article", "org", "person", "brand", "template", "bundle", "dataset"];
const STATUSES = [
  { value: "", label: "All" },
  { value: "adopted", label: "Adopted" },
  { value: "reviewed", label: "Available" },
  { value: "draft", label: "Draft" },
  { value: "archived", label: "Archived" },
];

function matchesQuery(item: AssetSummary, q: string): boolean {
  const needle = q.toLowerCase();
  if (item.slug.toLowerCase().includes(needle)) return true;
  if (item.title && item.title.toLowerCase().includes(needle)) return true;
  for (const t of item.tags) if (t.toLowerCase().includes(needle)) return true;
  return false;
}

export function CatalogBrowser({ allItems }: { allItems: AssetSummary[] }) {
  const searchParams = useSearchParams();
  const router = useRouter();

  const spKind   = searchParams.get("kind")   ?? undefined;
  const spStatus = searchParams.get("status") ?? undefined;
  const spQ      = searchParams.get("q")      ?? undefined;

  const filtered = useMemo(() => {
    let items = allItems;
    if (spKind)   items = items.filter((i) => i.kind === spKind);
    if (spStatus) items = items.filter((i) => i.status === spStatus);
    if (spQ)      items = items.filter((i) => matchesQuery(i, spQ));
    return items;
  }, [allItems, spKind, spStatus, spQ]);

  function buildHref(params: { kind?: string; status?: string; q?: string }): string {
    const usp = new URLSearchParams();
    if (params.kind)   usp.set("kind",   params.kind);
    if (params.status) usp.set("status", params.status);
    if (params.q)      usp.set("q",      params.q);
    const s = usp.toString();
    return `/catalog${s ? `?${s}` : ""}`;
  }

  function onSearchSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const q = (fd.get("q") as string | null) ?? "";
    router.push(buildHref({ kind: spKind, status: spStatus, q: q || undefined }));
  }

  return (
    <div className="space-y-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Catalog</h1>
          <p className="text-sm text-zinc-500 mt-1">
            All {allItems.length} catalog assets. For an action-oriented browse of
            adopted skills/agents/plugins/MCPs/prompts, use{" "}
            <Link href="/skills" className="underline">Skills &amp; Tools</Link>.
          </p>
        </div>
        <form onSubmit={onSearchSubmit} className="flex items-center gap-2">
          <input
            type="text"
            name="q"
            placeholder="search slug, title, tags"
            defaultValue={spQ ?? ""}
            className="px-3 py-1.5 text-sm border border-zinc-200 dark:border-zinc-800 rounded-md bg-white dark:bg-zinc-950 w-64"
          />
        </form>
      </header>

      <div className="space-y-2">
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="text-zinc-500 text-xs uppercase tracking-wider self-center mr-1">Kind:</span>
          <FilterLink label="all" current={spKind} value={undefined} kind status={spStatus} q={spQ} />
          {KINDS.map((k) => (
            <FilterLink key={k} label={k} value={k} current={spKind} kind status={spStatus} q={spQ} />
          ))}
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="text-zinc-500 text-xs uppercase tracking-wider self-center mr-1">Status:</span>
          {STATUSES.map(({ value, label }) => (
            <FilterLink
              key={value}
              label={label}
              value={value || undefined}
              current={spStatus}
              kindValue={spKind}
              q={spQ}
            />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {filtered.map((a) => (
          <AssetCard key={a.path} asset={a} hrefPrefix="/catalog" />
        ))}
      </div>
      {filtered.length === 0 && (
        <div className="text-sm text-zinc-500 py-6 text-center">
          No assets match. <Link href="/catalog" className="underline">Clear filters</Link>
        </div>
      )}
    </div>
  );
}

function FilterLink({
  label,
  value,
  current,
  kind,
  kindValue,
  status,
  q,
}: {
  label: string;
  value?: string;
  current?: string;
  // When `kind` is true, this link sets/clears the `kind` param.
  // When `kindValue` is set, this link sets/clears the `status` param (kind stays).
  kind?: boolean;
  kindValue?: string;
  status?: string;
  q?: string;
}) {
  const isActive = (value ?? "") === (current ?? "");
  const usp = new URLSearchParams();
  if (kind) {
    if (value)  usp.set("kind",   value);
    if (status) usp.set("status", status);
  } else {
    if (value)     usp.set("status", value);
    if (kindValue) usp.set("kind",   kindValue);
  }
  if (q) usp.set("q", q);
  const s = usp.toString();
  const url = `/catalog${s ? `?${s}` : ""}`;
  return (
    <Link
      href={url}
      className={`px-2.5 py-1 rounded-md border ${
        isActive
          ? "border-brand-500 bg-brand-50 dark:bg-zinc-800 text-brand-700 dark:text-zinc-100"
          : "border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 hover:border-zinc-400"
      }`}
    >
      {label}
    </Link>
  );
}
