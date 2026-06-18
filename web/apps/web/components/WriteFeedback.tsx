"use client";

import { ApiError } from "@/lib/api";

export function errorToBannerProps(e: unknown): { message: string; detail?: unknown } {
  if (e instanceof ApiError) {
    if (e.detail && typeof e.detail === "object") {
      const d = e.detail as { code?: string; message?: string };
      if (d.code) {
        return {
          message: d.message ? `${d.code}: ${d.message}` : d.code,
          detail: e.detail,
        };
      }
    }
    if (typeof e.detail === "string") return { message: e.detail };
    return { message: e.message };
  }
  if (e instanceof Error) return { message: e.message };
  return { message: String(e) };
}

export function VersionMismatchBanner({
  slug,
  expected,
  current,
  onReload,
}: {
  slug: string;
  expected: string;
  current: string;
  onReload?: () => void;
}) {
  return (
    <div className="rounded border border-amber-300 bg-amber-50 dark:bg-amber-950 dark:border-amber-800 p-3 text-sm space-y-2">
      <div className="font-medium text-amber-900 dark:text-amber-200">
        This file changed under you.
      </div>
      <div className="text-xs text-zinc-700 dark:text-zinc-300">
        <code className="font-mono">{slug}</code> was updated by another writer
        since you opened it. Reload to pick up the latest version before saving.
      </div>
      <div className="text-[11px] font-mono text-zinc-600 dark:text-zinc-400">
        expected: {expected.slice(0, 14) || "—"} · current:{" "}
        {current.slice(0, 14) || "—"}
      </div>
      {onReload && (
        <button
          type="button"
          onClick={onReload}
          className="rounded bg-amber-600 px-3 py-1 text-xs font-medium text-white hover:bg-amber-700"
        >
          Reload
        </button>
      )}
    </div>
  );
}
