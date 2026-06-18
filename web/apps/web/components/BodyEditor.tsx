"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, ApiError } from "@/lib/api";
import type { WriteResponse } from "@/lib/api-types";
import { VersionMismatchBanner, errorToBannerProps } from "./WriteFeedback";

export function BodyEditor({
  slug,
  initialBody,
  initialVersion,
}: {
  slug: string;
  initialBody: string;
  initialVersion: string;
}) {
  const router = useRouter();
  const [body, setBody] = useState(initialBody);
  const [version, setVersion] = useState(initialVersion);
  const [commitMessage, setCommitMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [ok, setOk] = useState<WriteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<{
    expected: string;
    current: string;
  } | null>(null);

  async function onSave() {
    setSaving(true);
    setOk(null);
    setError(null);
    setConflict(null);
    try {
      const res = await api.catalog.editBody(slug, {
        body,
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
  }

  async function reloadVersion() {
    try {
      const fresh = await api.catalog.raw(slug);
      setVersion(fresh.version);
      setBody(fresh.body);
      setConflict(null);
      router.refresh();
    } catch (e) {
      setError(errorToBannerProps(e).message);
    }
  }

  return (
    <div className="space-y-3">
      {conflict && (
        <VersionMismatchBanner
          slug={slug}
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs uppercase tracking-wider text-zinc-500 mb-1">
            Markdown source
          </label>
          <textarea
            className="form-input font-mono text-xs leading-snug"
            rows={Math.max(16, body.split("\n").length + 1)}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs uppercase tracking-wider text-zinc-500 mb-1">
            Preview
          </label>
          <div className="border border-zinc-200 dark:border-zinc-800 rounded p-3 prose-md max-w-none min-h-[200px]">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
          </div>
        </div>
      </div>

      <label className="block text-sm">
        <span className="block text-xs uppercase tracking-wider text-zinc-500 mb-1">
          Commit message (optional)
        </span>
        <input
          className="form-input"
          value={commitMessage}
          onChange={(e) => setCommitMessage(e.target.value)}
          placeholder={`web: edit catalog/${slug} body`}
        />
      </label>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onSave}
          disabled={saving}
          className="rounded bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save body"}
        </button>
        <span className="text-xs text-zinc-500 font-mono">
          version {version.slice(0, 10) || "—"}
        </span>
      </div>
    </div>
  );
}
