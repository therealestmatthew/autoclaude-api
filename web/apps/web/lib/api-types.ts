// Mirrors web/apps/api/models.py. Hand-maintained in v1 — when the API
// surface stabilizes (8.x), swap to openapi-typescript code-gen.

export type Bucket =
  | "catalog"
  | "queue"
  | "engagement"
  | "convention"
  | "plan"
  | "session_prompt"
  | "runbook"
  | "readme"
  | "claude"
  | "consulting"
  | "other";

export interface AssetSummary {
  path: string;
  bucket: Bucket;
  slug: string;
  kind: string | null;
  title: string | null;
  status: string | null;
  quality: number | null;
  tags: string[];
  created_at: string | null;
  updated_at: string | null;
  issues: string[];
}

export interface AssetDetail extends AssetSummary {
  body: string;
  source: Record<string, unknown> | null;
  discovered: Record<string, unknown> | null;
  relations: Record<string, unknown> | null;
}

export interface ListResponse {
  items: AssetSummary[];
  total: number;
}

export interface Stats {
  total: number;
  by_bucket: Record<string, number>;
  by_kind: Record<string, number>;
  by_status: Record<string, number>;
  with_issues: number;
}

export interface StatsResponse {
  stats: Stats;
  repo_root: string;
  snapshot_mtime: number;
}

export interface SearchHit extends AssetSummary {
  score: number;
  matched: string[];
}

export interface SearchResponse {
  query: string;
  hits: SearchHit[];
  total: number;
}

export interface ThreadEvent {
  date: string;
  thread_id: string | null;
  agent: string | null;
  started_at: string | null;
  ended_at: string | null;
  outcome: string | null;
  summary: string | null;
  model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  raw: Record<string, unknown>;
}

export interface ThreadResponse {
  events: ThreadEvent[];
  total: number;
  days_scanned: number;
}

export interface Health {
  ok: boolean;
  version: string;
  repo_root: string;
  records: number;
}
