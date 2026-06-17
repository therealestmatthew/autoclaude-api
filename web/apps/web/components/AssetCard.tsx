import Link from "next/link";
import type { AssetSummary } from "@/lib/api-types";
import { Badge } from "./Badge";

export function AssetCard({
  asset,
  hrefPrefix,
}: {
  asset: AssetSummary;
  hrefPrefix: string;
}) {
  return (
    <Link
      href={`${hrefPrefix}/${encodeURIComponent(asset.slug)}`}
      className="block p-4 border border-zinc-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-950 hover:border-brand-500 transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            {asset.kind && <Badge variant="kind">{asset.kind}</Badge>}
            {asset.status && <Badge variant="status">{asset.status}</Badge>}
            {asset.quality && (
              <span className="text-xs text-zinc-500">★ {asset.quality}</span>
            )}
          </div>
          <h3 className="font-medium text-zinc-900 dark:text-zinc-50 truncate">
            {asset.title ?? asset.slug}
          </h3>
          <div className="text-xs text-zinc-500 mt-0.5 truncate font-mono">
            {asset.slug}
          </div>
        </div>
        <div className="text-xs text-zinc-500 shrink-0 text-right">
          {asset.updated_at && <div>{asset.updated_at}</div>}
        </div>
      </div>
      {asset.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-3">
          {asset.tags.slice(0, 6).map((t) => (
            <Badge key={t} variant="tag">
              {t}
            </Badge>
          ))}
        </div>
      )}
      {asset.issues.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {asset.issues.map((i) => (
            <Badge key={i} variant="issue">
              {i}
            </Badge>
          ))}
        </div>
      )}
    </Link>
  );
}
