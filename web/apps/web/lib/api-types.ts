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
  // 8.3: optimistic-lock token. UI passes this back as
  // `expected_version` on any PUT/POST. Empty before first sync.
  version: string;
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

// ---------------------------------------------------------------------------
// 8.3 — write-back wire shapes
// ---------------------------------------------------------------------------

export interface EditFrontmatterRequest {
  frontmatter: Record<string, unknown>;
  expected_version: string;
  commit_message?: string | null;
}

export interface EditBodyRequest {
  body: string;
  expected_version: string;
  commit_message?: string | null;
}

export interface EditFullRequest {
  frontmatter: Record<string, unknown>;
  body: string;
  expected_version: string;
  commit_message?: string | null;
}

export interface WriteResponse {
  path: string;
  commit_sha: string;
  new_version: string;
  audit_id: string;
  commit_created: boolean;
}

export interface TriageRequest {
  action: "keep" | "merge" | "discard";
  expected_version: string;
  target_slug?: string | null;
  notes?: string | null;
  commit_message?: string | null;
}

export interface TriageResponse {
  action: "keep" | "merge" | "discard";
  source_path: string;
  target_path: string | null;
  commit_sha: string;
  new_version: string | null;
  audit_id: string;
  commit_created: boolean;
}

export interface ProposalSummary {
  id: string;
  created_at: number;
  source: string;
  target_path: string;
  target_bucket: string;
  action_kind: string;
  summary: string;
  confidence: number | null;
  status: string;
}

export interface ProposalDetail extends ProposalSummary {
  payload: Record<string, unknown>;
  rationale: string;
  decided_at: number | null;
  decided_by: string | null;
  decision_audit_id: string | null;
}

export interface ProposalListResponse {
  items: ProposalSummary[];
  total: number;
}

export interface AcceptProposalRequest {
  expected_version?: string | null;
}

export interface RejectProposalRequest {
  notes: string;
}

export interface AssetRaw {
  path: string;
  bucket: string;
  slug: string;
  frontmatter: Record<string, unknown>;
  body: string;
  version: string;
}
