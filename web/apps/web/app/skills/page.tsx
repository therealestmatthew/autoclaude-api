import { Suspense } from "react";
import { api } from "@/lib/api";
import { ApiBanner } from "@/components/ApiBanner";
import { SkillsBrowser } from "@/components/SkillsBrowser";
import type { AssetSummary } from "@/lib/api-types";

const SKILL_KINDS = ["agent", "skill", "plugin", "mcp", "prompt"] as const;

export default async function SkillsPage() {
  let items: AssetSummary[] = [];
  let fetchError = false;

  try {
    const results = await Promise.all(
      SKILL_KINDS.map((k) =>
        api.catalog.list({ kind: k, limit: 500 }).then((r) => r.items),
      ),
    );
    items = results.flat();
  } catch {
    fetchError = true;
  }

  if (fetchError) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Skills & Tools</h1>
        <ApiBanner />
      </div>
    );
  }

  return (
    <Suspense fallback={null}>
      <SkillsBrowser allItems={items} />
    </Suspense>
  );
}
