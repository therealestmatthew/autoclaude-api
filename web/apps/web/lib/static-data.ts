// Static data layer — reads the JSON bundle produced by
// `ft-autoclaude-export-static`. Used when NEXT_PUBLIC_STATIC_MODE=true,
// so server components can render at build time without a running API.
//
// Lives at: web/apps/web/public/data/
//   catalog.json           — { items: AssetSummary[], total }
//   conventions.json       — same shape
//   plans.json             — same shape
//   assets/<slug>.json     — AssetDetail
//   raw/<slug>.md          — original markdown file (for download)
//   slug-index.json        — { slug: { bucket, path, kind } } (drives generateStaticParams)
//   manifest.json          — build metadata

import { promises as fs } from "fs";
import path from "path";
import type { AssetDetail, AssetSummary, ListResponse } from "./api-types";

const DATA_DIR = path.join(process.cwd(), "public", "data");

type CatalogFile = { items: AssetSummary[]; total: number };

async function readJson<T>(rel: string): Promise<T> {
  const p = path.join(DATA_DIR, rel);
  const raw = await fs.readFile(p, "utf-8");
  return JSON.parse(raw) as T;
}

function matchesQuery(item: AssetSummary, q: string): boolean {
  const needle = q.toLowerCase();
  if (item.slug.toLowerCase().includes(needle)) return true;
  if (item.title && item.title.toLowerCase().includes(needle)) return true;
  for (const t of item.tags) if (t.toLowerCase().includes(needle)) return true;
  return false;
}

function applyFilters(
  items: AssetSummary[],
  filters: { kind?: string; status?: string; tag?: string; q?: string },
): AssetSummary[] {
  let out = items;
  if (filters.kind)   out = out.filter((i) => i.kind === filters.kind);
  if (filters.status) out = out.filter((i) => i.status === filters.status);
  if (filters.tag)    out = out.filter((i) => i.tags.includes(filters.tag!));
  if (filters.q)      out = out.filter((i) => matchesQuery(i, filters.q!));
  return out;
}

function paginate<T>(items: T[], offset = 0, limit = 500): T[] {
  return items.slice(offset, offset + limit);
}

export const staticData = {
  catalog: {
    list: async (params: {
      kind?: string;
      status?: string;
      tag?: string;
      q?: string;
      offset?: number;
      limit?: number;
    } = {}): Promise<ListResponse> => {
      const file = await readJson<CatalogFile>("catalog.json");
      const filtered = applyFilters(file.items, params);
      const page = paginate(filtered, params.offset ?? 0, params.limit ?? 500);
      return { items: page, total: filtered.length };
    },
    get: async (slug: string): Promise<AssetDetail> => {
      try {
        return await readJson<AssetDetail>(`assets/${slug}.json`);
      } catch (e) {
        const err = new Error(`GET /catalog/${slug} -> 404`);
        (err as Error & { status?: number }).status = 404;
        throw err;
      }
    },
  },
  conventions: {
    list: async (): Promise<ListResponse> => readJson("conventions.json"),
    get: async (slug: string): Promise<AssetDetail> => readJson(`assets/${slug}.json`),
  },
  plans: {
    list: async (): Promise<ListResponse> => readJson("plans.json"),
    get: async (slug: string): Promise<AssetDetail> => readJson(`assets/${slug}.json`),
  },

  // For `generateStaticParams` — all detail-route slugs known to the bundle.
  allSlugs: async (
    buckets: string[] = ["catalog"],
  ): Promise<{ slug: string; bucket: string; kind: string | null }[]> => {
    const idx = await readJson<Record<string, { bucket: string; kind: string | null }>>(
      "slug-index.json",
    );
    return Object.entries(idx)
      .filter(([, v]) => buckets.includes(v.bucket))
      .map(([slug, v]) => ({ slug, bucket: v.bucket, kind: v.kind }));
  },
};

export const STATIC_MODE = process.env.NEXT_PUBLIC_STATIC_MODE === "true";
