"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { AssetRaw, WriteResponse } from "@/lib/api-types";
import { VersionMismatchBanner, errorToBannerProps } from "./WriteFeedback";

const KINDS = [
  "",
  "agent",
  "skill",
  "plugin",
  "mcp",
  "prompt",
  "repo",
  "article",
  "person",
  "org",
] as const;

const STATUSES = ["draft", "reviewed", "adopted", "archived"] as const;

const TYPED_KEYS = [
  "name",
  "title",
  "kind",
  "status",
  "quality",
  "tags",
  "source",
  "discovered",
  "relations",
];

function parseTags(input: string): string[] {
  return input
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function jsonOrNull(
  text: string,
): { ok: true; value: unknown } | { ok: false; error: string } {
  const trimmed = text.trim();
  if (!trimmed) return { ok: true, value: null };
  try {
    return { ok: true, value: JSON.parse(trimmed) };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "invalid JSON" };
  }
}

function pickExtras(fm: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(fm)) {
    if (!TYPED_KEYS.includes(k)) out[k] = v;
  }
  return out;
}

function asString(v: unknown): string {
  return typeof v === "string" ? v : "";
}

function asNumberString(v: unknown): string {
  return typeof v === "number" ? String(v) : "";
}

function asStringArray(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is string => typeof x === "string");
}

export function FrontmatterForm({ raw }: { raw: AssetRaw }) {
  const router = useRouter();
  const fm = raw.frontmatter;
  const [title, setTitle] = useState(asString(fm.title));
  const [kind, setKind] = useState(asString(fm.kind));
  const [status, setStatus] = useState(asString(fm.status) || "draft");
  const [quality, setQuality] = useState(asNumberString(fm.quality));
  const [tags, setTags] = useState(asStringArray(fm.tags).join(", "));
  const [sourceJson, setSourceJson] = useState(
    JSON.stringify(fm.source ?? {}, null, 2),
  );
  const [discoveredJson, setDiscoveredJson] = useState(
    JSON.stringify(fm.discovered ?? {}, null, 2),
  );
  const [relationsJson, setRelationsJson] = useState(
    JSON.stringify(fm.relations ?? {}, null, 2),
  );
  const [extrasJson, setExtrasJson] = useState(
    JSON.stringify(pickExtras(fm), null, 2),
  );
  const [commitMessage, setCommitMessage] = useState("");
  const [version, setVersion] = useState(raw.version);
  const [saving, setSaving] = useState(false);
  const [ok, setOk] = useState<WriteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<{
    expected: string;
    current: string;
  } | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setOk(null);
    setError(null);
    setConflict(null);

    const source = jsonOrNull(sourceJson);
    if (!source.ok) return fail(`source: ${source.error}`);
    const discovered = jsonOrNull(discoveredJson);
    if (!discovered.ok) return fail(`discovered: ${discovered.error}`);
    const relations = jsonOrNull(relationsJson);
    if (!relations.ok) return fail(`relations: ${relations.error}`);
    const extras = jsonOrNull(extrasJson);
    if (!extras.ok) return fail(`extras: ${extras.error}`);

    const extrasDict =
      extras.value && typeof extras.value === "object" && !Array.isArray(extras.value)
        ? (extras.value as Record<string, unknown>)
        : {};

    const frontmatter: Record<string, unknown> = {
      ...extrasDict,
      name: raw.slug,
    };
    if (title) frontmatter.title = title;
    if (kind) frontmatter.kind = kind;
    if (status) frontmatter.status = status;
    if (quality.trim()) {
      const q = Number(quality);
      if (!Number.isFinite(q)) return fail("quality: must be a number");
      frontmatter.quality = q;
    }
    const tagList = parseTags(tags);
    if (tagList.length > 0) frontmatter.tags = tagList;
    if (
      source.value &&
      typeof source.value === "object" &&
      Object.keys(source.value as object).length > 0
    ) {
      frontmatter.source = source.value;
    }
    if (
      discovered.value &&
      typeof discovered.value === "object" &&
      Object.keys(discovered.value as object).length > 0
    ) {
      frontmatter.discovered = discovered.value;
    }
    if (
      relations.value &&
      typeof relations.value === "object" &&
      Object.keys(relations.value as object).length > 0
    ) {
      frontmatter.relations = relations.value;
    }

    try {
      const res = await api.catalog.editFrontmatter(raw.slug, {
        frontmatter,
        expected_version: version,
        commit_message: commitMessage || null,
      });
      setOk(res);
      setVersion(res.new_version);
      router.refresh();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const d = e.detail as { code?: string; expected?: string; current?: string };
        if (d?.code === "version-mismatch") {
          setConflict({
            expected: d.expected ?? version,
            current: d.current ?? "",
          });
        } else {
          setError(errorToBannerProps(e).message);
        }
      } else {
        setError(errorToBannerProps(e).message);
      }
    } finally {
      setSaving(false);
    }

    function fail(msg: string) {
      setError(msg);
      setSaving(false);
    }
  }

  async function reloadVersion() {
    try {
      const fresh = await api.catalog.raw(raw.slug);
      setVersion(fresh.version);
      setConflict(null);
      router.refresh();
    } catch (e) {
      setError(errorToBannerProps(e).message);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      {conflict && (
        <VersionMismatchBanner
          slug={raw.slug}
          expected={conflict.expected}
          current={conflict.current}
          onReload={reloadVersion}
        />
      )}
      {ok && (
        <div className="rounded border border-emerald-300 bg-emerald-50 dark:bg-emerald-950 dark:border-emerald-800 p-3 text-sm">
          Saved — commit{" "}
          <code className="font-mono">{ok.commit_sha.slice(0, 10)}</code>
          {!ok.commit_created && " (no-op)"} · audit{" "}
          <code className="font-mono">{ok.audit_id.slice(0, 8)}</code>
        </div>
      )}
      {error && (
        <div className="rounded border border-rose-300 bg-rose-50 dark:bg-rose-950 dark:border-rose-800 p-3 text-sm text-rose-900 dark:text-rose-200">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Field label="Title">
          <input
            className="form-input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </Field>
        <Field label="Kind">
          <select
            className="form-input"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {k || "—"}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Status">
          <select
            className="form-input"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Quality (1–5)">
          <input
            className="form-input"
            inputMode="numeric"
            value={quality}
            onChange={(e) => setQuality(e.target.value)}
            placeholder="—"
          />
        </Field>
        <Field label="Tags (comma-separated)" wide>
          <input
            className="form-input"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
          />
        </Field>
      </div>

      <JsonField label="source" value={sourceJson} onChange={setSourceJson} />
      <JsonField
        label="discovered"
        value={discoveredJson}
        onChange={setDiscoveredJson}
      />
      <JsonField
        label="relations"
        value={relationsJson}
        onChange={setRelationsJson}
      />
      <JsonField
        label="extras (other frontmatter keys; preserved verbatim)"
        value={extrasJson}
        onChange={setExtrasJson}
      />

      <Field label="Commit message (optional)">
        <input
          className="form-input"
          value={commitMessage}
          onChange={(e) => setCommitMessage(e.target.value)}
          placeholder={`web: edit catalog/${raw.slug} frontmatter`}
        />
      </Field>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={saving}
          className="rounded bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save frontmatter"}
        </button>
        <span className="text-xs text-zinc-500 font-mono">
          version {version.slice(0, 10) || "—"}
        </span>
      </div>
    </form>
  );
}

function Field({
  label,
  children,
  wide,
}: {
  label: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <label className={`block text-sm ${wide ? "md:col-span-2" : ""}`}>
      <span className="block text-xs uppercase tracking-wider text-zinc-500 mb-1">
        {label}
      </span>
      {children}
    </label>
  );
}

function JsonField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="block text-sm">
      <span className="block text-xs uppercase tracking-wider text-zinc-500 mb-1">
        {label}
      </span>
      <textarea
        className="form-input font-mono text-xs leading-snug"
        rows={Math.max(3, value.split("\n").length)}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
