import Link from "next/link";
import type { AssetSummary } from "@/lib/api-types";
import { Badge } from "./Badge";

const KIND_ICON: Record<string, string> = {
  agent: "🤖",
  skill: "⚡",
  plugin: "🔌",
  mcp: "🔧",
  prompt: "💬",
};

const FUNCTION_LABEL: Record<string, string> = {
  discovery:    "Discovery",
  requirements: "Requirements",
  architecture: "Architecture",
  build:        "Build",
  integration:  "Integration",
  testing:      "Testing",
  deployment:   "Deployment",
  training:     "Training",
  "change-mgmt": "Change Mgmt",
  reporting:    "Reporting",
};

function adoptionBorder(status: string | null): string {
  switch (status) {
    case "adopted":
      return "border-l-emerald-500";
    case "reviewed":
      return "border-l-blue-400";
    case "archived":
      return "border-l-zinc-400";
    default:
      return "border-l-amber-400";
  }
}

function adoptionLabel(status: string | null): { text: string; cls: string } {
  switch (status) {
    case "adopted":
      return { text: "Adopted", cls: "text-emerald-600 dark:text-emerald-400" };
    case "reviewed":
      return { text: "Available", cls: "text-blue-600 dark:text-blue-400" };
    case "archived":
      return { text: "Archived", cls: "text-zinc-500" };
    default:
      return { text: "Draft", cls: "text-amber-600 dark:text-amber-400" };
  }
}

export function SkillCard({ asset }: { asset: AssetSummary }) {
  const icon = KIND_ICON[asset.kind ?? ""] ?? "📦";
  const { text: adoptText, cls: adoptCls } = adoptionLabel(asset.status);

  return (
    <Link
      href={`/skills/${encodeURIComponent(asset.slug)}`}
      className={`block p-4 border border-zinc-200 dark:border-zinc-800 border-l-4 ${adoptionBorder(asset.status)} rounded-lg bg-white dark:bg-zinc-950 hover:border-brand-500 hover:border-l-4 transition-colors`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-base leading-none">{icon}</span>
            {asset.kind && <Badge variant="kind">{asset.kind}</Badge>}
            <span className={`text-xs font-medium ${adoptCls}`}>{adoptText}</span>
            {asset.quality !== null && asset.quality >= 4 && (
              <span className="text-xs text-amber-500 font-medium">
                {"★".repeat(asset.quality)}
              </span>
            )}
          </div>
          <h3 className="font-medium text-zinc-900 dark:text-zinc-50 truncate leading-snug">
            {asset.title ?? asset.slug}
          </h3>
          <div className="text-xs text-zinc-400 mt-0.5 truncate font-mono">
            {asset.slug}
          </div>
        </div>
        {asset.quality !== null && asset.quality < 4 && (
          <div className="text-xs text-zinc-400 shrink-0">★ {asset.quality}</div>
        )}
      </div>

      {(asset.delivery_functions ?? []).length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {(asset.delivery_functions ?? []).map((fn) => (
            <span
              key={fn}
              className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-violet-50 text-violet-700 dark:bg-violet-950 dark:text-violet-300 border border-violet-200 dark:border-violet-800"
            >
              {FUNCTION_LABEL[fn] ?? fn}
            </span>
          ))}
        </div>
      )}

      {asset.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {asset.tags.slice(0, 5).map((t) => (
            <Badge key={t} variant="tag">{t}</Badge>
          ))}
        </div>
      )}

      {asset.issues.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {asset.issues.map((i) => (
            <Badge key={i} variant="issue">{i}</Badge>
          ))}
        </div>
      )}
    </Link>
  );
}
