"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { TriageResponse } from "@/lib/api-types";
import { VersionMismatchBanner, errorToBannerProps } from "./WriteFeedback";

type Action = "keep" | "merge" | "discard";

export function TriagePanel({
  slug,
  initialVersion,
}: {
  slug: string;
  initialVersion: string;
}) {
  const router = useRouter();
  const [version, setVersion] = useState(initialVersion);
  const [action, setAction] = useState<Action>("keep");
  const [targetSlug, setTargetSlug] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [ok, setOk] = useState<TriageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<{
    expected: string;
    current: string;
  } | null>(null);

  async function onSubmit() {
    setSubmitting(true);
    setOk(null);
    setError(null);
    setConflict(null);

    if (action === "merge" && !targetSlug.trim()) {
      setError("target slug is required for merge");
      setSubmitting(false);
      return;
    }
    if (action === "discard" && !notes.trim()) {
      setError("notes are required for discard");
      setSubmitting(false);
      return;
    }

    try {
      const res = await api.queue.triage(slug, {
        action,
        expected_version: version,
        target_slug:
          action === "discard" ? null : targetSlug.trim() || null,
        notes: notes.trim() || null,
        commit_message: null,
      });
      setOk(res);
      if (res.new_version) setVersion(res.new_version);
      router.refresh();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const d = e.detail as { code?: string; expected?: string; current?: string; message?: string };
        if (d?.code === "version-mismatch") {
          setConflict({
            expected: d.expected ?? version,
            current: d.current ?? "",
          });
        } else if (d?.code === "target-exists") {
          setError(`target-exists: ${d.message ?? "catalog slug already taken"}`);
        } else {
          setError(errorToBannerProps(e).message);
        }
      } else {
        setError(errorToBannerProps(e).message);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function reloadVersion() {
    try {
      const fresh = await api.queue.get(slug);
      setVersion(fresh.version);
      setConflict(null);
      router.refresh();
    } catch (e) {
      setError(errorToBannerProps(e).message);
    }
  }

  if (ok) {
    return (
      <div className="rounded border border-emerald-300 bg-emerald-50 dark:bg-emerald-950 dark:border-emerald-800 p-3 text-sm space-y-1">
        <div className="font-medium text-emerald-900 dark:text-emerald-200">
          Triaged: {ok.action}
        </div>
        <div className="text-xs">
          commit{" "}
          <code className="font-mono">{ok.commit_sha.slice(0, 10)}</code>
          {!ok.commit_created && " (no-op)"} · audit{" "}
          <code className="font-mono">{ok.audit_id.slice(0, 8)}</code>
        </div>
        {ok.target_path && (
          <div className="text-xs">
            target:{" "}
            {ok.action === "discard" ? (
              <code className="font-mono">{ok.target_path}</code>
            ) : (
              <Link
                href={`/catalog/${pathToSlug(ok.target_path)}`}
                className="text-brand-700 hover:underline font-mono"
              >
                {ok.target_path}
              </Link>
            )}
          </div>
        )}
        <div>
          <Link href="/queue" className="text-xs text-brand-700 hover:underline">
            ← back to queue
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3 border border-zinc-200 dark:border-zinc-800 rounded p-4">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-medium">Triage</h2>
        <span className="text-xs text-zinc-500 font-mono">
          version {version.slice(0, 10) || "—"}
        </span>
      </div>

      {conflict && (
        <VersionMismatchBanner
          slug={slug}
          expected={conflict.expected}
          current={conflict.current}
          onReload={reloadVersion}
        />
      )}

      <div className="flex flex-wrap gap-2">
        {(["keep", "merge", "discard"] as const).map((a) => (
          <button
            key={a}
            type="button"
            onClick={() => setAction(a)}
            className={`rounded px-3 py-1.5 text-sm border ${
              action === a
                ? "bg-brand-600 border-brand-600 text-white"
                : "bg-white dark:bg-zinc-900 border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 hover:border-brand-500"
            }`}
          >
            {a}
          </button>
        ))}
      </div>

      {(action === "keep" || action === "merge") && (
        <label className="block text-sm">
          <span className="block text-xs uppercase tracking-wider text-zinc-500 mb-1">
            {action === "keep"
              ? "Target catalog slug (optional — defaults to current slug)"
              : "Target catalog slug (required — existing asset to merge into)"}
          </span>
          <input
            className="form-input"
            value={targetSlug}
            onChange={(e) => setTargetSlug(e.target.value)}
            placeholder={action === "merge" ? "existing-catalog-slug" : slug}
          />
        </label>
      )}

      <label className="block text-sm">
        <span className="block text-xs uppercase tracking-wider text-zinc-500 mb-1">
          Notes{action === "discard" ? " (required)" : " (optional)"}
        </span>
        <textarea
          className="form-input"
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder={
            action === "discard"
              ? "Why are we discarding? This is recorded in the audit log."
              : ""
          }
        />
      </label>

      {error && (
        <div className="rounded border border-rose-300 bg-rose-50 dark:bg-rose-950 dark:border-rose-800 p-3 text-sm text-rose-900 dark:text-rose-200">
          {error}
        </div>
      )}

      <button
        type="button"
        onClick={onSubmit}
        disabled={submitting}
        className="rounded bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
      >
        {submitting ? "Submitting…" : `Submit ${action}`}
      </button>
    </div>
  );
}

function pathToSlug(path: string): string {
  const base = path.split("/").pop() ?? "";
  return base.replace(/\.md$/, "");
}
