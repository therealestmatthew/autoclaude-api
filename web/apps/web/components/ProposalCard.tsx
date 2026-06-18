"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { ProposalSummary } from "@/lib/api-types";
import { errorToBannerProps } from "./WriteFeedback";

export function ProposalCard({
  proposal,
  rationale,
}: {
  proposal: ProposalSummary;
  rationale?: string;
}) {
  const router = useRouter();
  const [rejectNotes, setRejectNotes] = useState("");
  const [showReject, setShowReject] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<string | null>(null);

  async function onAccept() {
    setBusy(true);
    setError(null);
    try {
      await api.proposals.accept(proposal.id, {});
      setOutcome("accepted");
      router.refresh();
    } catch (e) {
      setError(toMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function onReject() {
    if (!rejectNotes.trim()) {
      setError("notes are required");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.proposals.reject(proposal.id, { notes: rejectNotes.trim() });
      setOutcome("rejected");
      router.refresh();
    } catch (e) {
      setError(toMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const isPending = proposal.status === "pending" && !outcome;
  const targetSlug = pathToSlug(proposal.target_path);
  const targetHref = `/${proposal.target_bucket}/${targetSlug}`;

  return (
    <div className="rounded border border-zinc-200 dark:border-zinc-800 p-3 space-y-2 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1 min-w-0">
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <span className="rounded bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 font-mono">
              {proposal.action_kind}
            </span>
            <span className="rounded bg-indigo-100 dark:bg-indigo-950 text-indigo-800 dark:text-indigo-200 px-1.5 py-0.5">
              {proposal.source}
            </span>
            {proposal.confidence != null && (
              <span className="text-xs">
                {(proposal.confidence * 100).toFixed(0)}%
              </span>
            )}
            <span className="text-xs">{statusLabel(outcome ?? proposal.status)}</span>
          </div>
          <div className="font-medium">{proposal.summary}</div>
          <Link
            href={targetHref}
            className="block text-xs text-brand-700 hover:underline font-mono truncate"
          >
            {proposal.target_path}
          </Link>
          {rationale && (
            <details className="text-xs text-zinc-600 dark:text-zinc-400">
              <summary className="cursor-pointer select-none">
                rationale
              </summary>
              <div className="mt-1 whitespace-pre-wrap">{rationale}</div>
            </details>
          )}
        </div>
        {isPending && (
          <div className="flex flex-col gap-2 shrink-0">
            <button
              type="button"
              onClick={onAccept}
              disabled={busy}
              className="rounded bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {busy ? "…" : "Accept"}
            </button>
            <button
              type="button"
              onClick={() => setShowReject((v) => !v)}
              disabled={busy}
              className="rounded border border-zinc-300 dark:border-zinc-700 px-3 py-1 text-xs hover:bg-zinc-50 dark:hover:bg-zinc-900"
            >
              Reject
            </button>
          </div>
        )}
      </div>

      {isPending && showReject && (
        <div className="space-y-2 border-t border-zinc-200 dark:border-zinc-800 pt-2">
          <textarea
            className="form-input text-xs"
            rows={2}
            value={rejectNotes}
            onChange={(e) => setRejectNotes(e.target.value)}
            placeholder="Why reject? (recorded in audit log)"
          />
          <button
            type="button"
            onClick={onReject}
            disabled={busy}
            className="rounded bg-rose-600 px-3 py-1 text-xs font-medium text-white hover:bg-rose-700 disabled:opacity-50"
          >
            {busy ? "Submitting…" : "Confirm reject"}
          </button>
        </div>
      )}

      {error && (
        <div className="rounded border border-rose-300 bg-rose-50 dark:bg-rose-950 dark:border-rose-800 p-2 text-xs text-rose-900 dark:text-rose-200">
          {error}
        </div>
      )}
    </div>
  );
}

function toMessage(e: unknown): string {
  if (e instanceof ApiError) {
    return errorToBannerProps(e).message;
  }
  return e instanceof Error ? e.message : String(e);
}

function statusLabel(status: string): string {
  return status;
}

function pathToSlug(path: string): string {
  const base = path.split("/").pop() ?? "";
  return base.replace(/\.md$/, "");
}
