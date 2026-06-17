// Typed FastAPI client. Used from Server Components — see app/*/page.tsx.
// Client-side fetches go through the same helpers to keep error handling
// uniform.

import type {
  AssetDetail,
  Health,
  ListResponse,
  SearchResponse,
  StatsResponse,
  ThreadResponse,
} from "./api-types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly url: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function get<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    // Always hit a live backend in v1 — never use Next.js's data cache,
    // since the underlying markdown can change between requests.
    cache: "no-store",
    ...init,
  });
  if (!res.ok) {
    throw new ApiError(`GET ${path} -> ${res.status}`, res.status, url);
  }
  return (await res.json()) as T;
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

export const api = {
  base: API_BASE,

  health: () => get<Health>("/health"),

  stats: () => get<StatsResponse>("/stats"),

  catalog: {
    list: (params: {
      kind?: string;
      status?: string;
      tag?: string;
      q?: string;
      offset?: number;
      limit?: number;
    } = {}) => get<ListResponse>(`/catalog${qs(params)}`),
    get: (slug: string) => get<AssetDetail>(`/catalog/${encodeURIComponent(slug)}`),
  },

  queue: {
    list: (params: {
      kind?: string;
      q?: string;
      offset?: number;
      limit?: number;
    } = {}) => get<ListResponse>(`/queue${qs(params)}`),
    get: (slug: string) => get<AssetDetail>(`/queue/${encodeURIComponent(slug)}`),
  },

  engagements: {
    list: (params: { status?: string; q?: string } = {}) =>
      get<ListResponse>(`/engagements${qs(params)}`),
    get: (slug: string) =>
      get<AssetDetail>(`/engagements/${encodeURIComponent(slug)}`),
  },

  conventions: {
    list: () => get<ListResponse>("/conventions"),
    get: (slug: string) =>
      get<AssetDetail>(`/conventions/${encodeURIComponent(slug)}`),
  },

  plans: {
    list: () => get<ListResponse>("/plans"),
    get: (slug: string) => get<AssetDetail>(`/plans/${encodeURIComponent(slug)}`),
  },

  threads: {
    list: (params: {
      date?: string;
      since?: string;
      until?: string;
      agent?: string;
      outcome?: string;
      limit?: number;
    } = {}) => get<ThreadResponse>(`/threads${qs(params)}`),
    recent: (params: { limit?: number; days?: number } = {}) =>
      get<ThreadResponse>(`/threads/recent${qs(params)}`),
  },

  search: (params: { q: string; bucket?: string; limit?: number }) =>
    get<SearchResponse>(`/search${qs(params)}`),
};
