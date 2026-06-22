// Typed FastAPI client. Used from Server Components — see app/*/page.tsx.
// Client-side fetches go through the same helpers to keep error handling
// uniform.

import type {
  AcceptProposalRequest,
  AssetDetail,
  AssetRaw,
  BusinessProcessItem,
  BusinessProcessListResponse,
  ClientCreate,
  ClientItem,
  ClientListResponse,
  ClientUpdate,
  EditBodyRequest,
  EditFrontmatterRequest,
  EditFullRequest,
  Health,
  ListResponse,
  ProposalDetail,
  ProposalListResponse,
  RejectProposalRequest,
  SearchResponse,
  StatsResponse,
  ThreadResponse,
  TimelineDetail,
  TimelineListResponse,
  TriageRequest,
  TriageResponse,
  WriteResponse,
} from "./api-types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const STATIC_MODE = process.env.NEXT_PUBLIC_STATIC_MODE === "true";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly url: string,
    public readonly detail?: unknown,
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

async function send<T>(
  method: "PUT" | "POST" | "DELETE",
  path: string,
  body?: unknown,
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    method,
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }
  if (!res.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? (payload as { detail: unknown }).detail
        : payload;
    throw new ApiError(
      `${method} ${path} -> ${res.status}`,
      res.status,
      url,
      detail,
    );
  }
  return payload as T;
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

  stats: async (): Promise<StatsResponse> => {
    if (STATIC_MODE) {
      // Best-effort stats from the bundled catalog file. Avoids a 404 on
      // the dashboard when there's no API server at build time.
      const { staticData } = await import("./static-data");
      const list = await staticData.catalog.list({ limit: 10000 });
      const by_kind: Record<string, number> = {};
      const by_status: Record<string, number> = {};
      for (const i of list.items) {
        if (i.kind) by_kind[i.kind] = (by_kind[i.kind] ?? 0) + 1;
        if (i.status) by_status[i.status] = (by_status[i.status] ?? 0) + 1;
      }
      return {
        stats: {
          total: list.total,
          by_bucket: { catalog: list.total },
          by_kind,
          by_status,
          with_issues: 0,
        },
        repo_root: "",
        snapshot_mtime: 0,
      };
    }
    return get<StatsResponse>("/stats");
  },

  catalog: {
    list: async (params: {
      kind?: string;
      status?: string;
      tag?: string;
      q?: string;
      offset?: number;
      limit?: number;
    } = {}) => {
      if (STATIC_MODE) {
        const { staticData } = await import("./static-data");
        return staticData.catalog.list(params);
      }
      return get<ListResponse>(`/catalog${qs(params)}`);
    },
    get: async (slug: string) => {
      if (STATIC_MODE) {
        const { staticData } = await import("./static-data");
        return staticData.catalog.get(slug);
      }
      return get<AssetDetail>(`/catalog/${encodeURIComponent(slug)}`);
    },
    raw: (slug: string) => get<AssetRaw>(`/catalog/${encodeURIComponent(slug)}/raw`),
    editFull: (slug: string, body: EditFullRequest) =>
      send<WriteResponse>("PUT", `/catalog/${encodeURIComponent(slug)}`, body),
    editFrontmatter: (slug: string, body: EditFrontmatterRequest) =>
      send<WriteResponse>(
        "PUT",
        `/catalog/${encodeURIComponent(slug)}/frontmatter`,
        body,
      ),
    editBody: (slug: string, body: EditBodyRequest) =>
      send<WriteResponse>(
        "PUT",
        `/catalog/${encodeURIComponent(slug)}/body`,
        body,
      ),
  },

  queue: {
    list: async (params: {
      kind?: string;
      q?: string;
      offset?: number;
      limit?: number;
    } = {}) => {
      if (STATIC_MODE) return { items: [], total: 0 } as ListResponse;
      return get<ListResponse>(`/queue${qs(params)}`);
    },
    get: (slug: string) => get<AssetDetail>(`/queue/${encodeURIComponent(slug)}`),
    triage: (slug: string, body: TriageRequest) =>
      send<TriageResponse>(
        "POST",
        `/queue/${encodeURIComponent(slug)}/triage`,
        body,
      ),
  },

  proposals: {
    list: async (params: {
      status?: string;
      source?: string;
      target_bucket?: string;
      target_path?: string;
      limit?: number;
      offset?: number;
    } = {}) => {
      if (STATIC_MODE) return { items: [], total: 0 } as ProposalListResponse;
      return get<ProposalListResponse>(`/proposals${qs(params)}`);
    },
    get: (id: string) => get<ProposalDetail>(`/proposals/${encodeURIComponent(id)}`),
    accept: (id: string, body: AcceptProposalRequest = {}) =>
      send<TriageResponse>(
        "POST",
        `/proposals/${encodeURIComponent(id)}/accept`,
        body,
      ),
    reject: (id: string, body: RejectProposalRequest) =>
      send<ProposalDetail>(
        "POST",
        `/proposals/${encodeURIComponent(id)}/reject`,
        body,
      ),
  },

  engagements: {
    list: async (params: { status?: string; q?: string } = {}) => {
      if (STATIC_MODE) return { items: [], total: 0 } as ListResponse;
      return get<ListResponse>(`/engagements${qs(params)}`);
    },
    get: (slug: string) =>
      get<AssetDetail>(`/engagements/${encodeURIComponent(slug)}`),
  },

  conventions: {
    list: async () => {
      if (STATIC_MODE) {
        const { staticData } = await import("./static-data");
        return staticData.conventions.list();
      }
      return get<ListResponse>("/conventions");
    },
    get: async (slug: string) => {
      if (STATIC_MODE) {
        const { staticData } = await import("./static-data");
        return staticData.conventions.get(slug);
      }
      return get<AssetDetail>(`/conventions/${encodeURIComponent(slug)}`);
    },
  },

  plans: {
    list: async () => {
      if (STATIC_MODE) {
        const { staticData } = await import("./static-data");
        return staticData.plans.list();
      }
      return get<ListResponse>("/plans");
    },
    get: async (slug: string) => {
      if (STATIC_MODE) {
        const { staticData } = await import("./static-data");
        return staticData.plans.get(slug);
      }
      return get<AssetDetail>(`/plans/${encodeURIComponent(slug)}`);
    },
  },

  threads: {
    list: async (params: {
      date?: string;
      since?: string;
      until?: string;
      agent?: string;
      outcome?: string;
      limit?: number;
    } = {}) => {
      if (STATIC_MODE) return { events: [], total: 0, days_scanned: 0 } as ThreadResponse;
      return get<ThreadResponse>(`/threads${qs(params)}`);
    },
    recent: async (params: { limit?: number; days?: number } = {}) => {
      if (STATIC_MODE) return { events: [], total: 0, days_scanned: 0 } as ThreadResponse;
      return get<ThreadResponse>(`/threads/recent${qs(params)}`);
    },
  },

  search: async (params: { q: string; bucket?: string; limit?: number }) => {
    if (STATIC_MODE) {
      // In static mode, run the search against the bundled catalog file.
      const { staticData } = await import("./static-data");
      const list = await staticData.catalog.list({ q: params.q, limit: params.limit ?? 200 });
      return {
        query: params.q,
        hits: list.items.map((i) => ({ ...i, score: 1, matched: [] })),
        total: list.total,
      } as SearchResponse;
    }
    return get<SearchResponse>(`/search${qs(params)}`);
  },

  brands: {
    list: async (params: { status?: string; q?: string } = {}) => {
      if (STATIC_MODE) return { items: [], total: 0 } as ListResponse;
      return get<ListResponse>(`/brands${qs(params)}`);
    },
    get: (slug: string) =>
      get<AssetDetail>(`/brands/${encodeURIComponent(slug)}`),
  },

  clients: {
    list: async (params: { q?: string; offset?: number; limit?: number } = {}) => {
      if (STATIC_MODE) return { items: [], total: 0 } as ClientListResponse;
      return get<ClientListResponse>(`/clients${qs(params)}`);
    },
    get: (slug: string) =>
      get<ClientItem>(`/clients/${encodeURIComponent(slug)}`),
    create: (body: ClientCreate) =>
      send<ClientItem>("POST", "/clients", body),
    update: (slug: string, body: ClientUpdate) =>
      send<ClientItem>("PUT", `/clients/${encodeURIComponent(slug)}`, body),
    delete: (slug: string) =>
      send<void>("DELETE", `/clients/${encodeURIComponent(slug)}`),
  },

  processes: {
    list: async (params: { q?: string } = {}) => {
      if (STATIC_MODE) return { items: [], total: 0 } as BusinessProcessListResponse;
      return get<BusinessProcessListResponse>(`/processes${qs(params)}`);
    },
    get: (slug: string) =>
      get<BusinessProcessItem>(`/processes/${encodeURIComponent(slug)}`),
  },

  timelines: {
    list: async () => {
      if (STATIC_MODE) return { items: [], total: 0 } as TimelineListResponse;
      return get<TimelineListResponse>("/timelines");
    },
    get: (slug: string) =>
      get<TimelineDetail>(`/timelines/${encodeURIComponent(slug)}`),
  },
};
