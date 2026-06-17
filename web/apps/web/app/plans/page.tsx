import Link from "next/link";
import { api } from "@/lib/api";
import { ApiBanner } from "@/components/ApiBanner";
import { Badge } from "@/components/Badge";

export const dynamic = "force-dynamic";

export default async function PlansPage() {
  let list;
  try {
    list = await api.plans.list();
  } catch {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Plans</h1>
        <ApiBanner />
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Phase plans</h1>
        <p className="text-sm text-zinc-500 mt-1">
          The design lineage of the program — every meaningful decision.
        </p>
      </header>
      <ul className="space-y-2">
        {list.items.map((p) => (
          <li
            key={p.path}
            className="border border-zinc-200 dark:border-zinc-800 rounded-lg"
          >
            <Link
              href={`/plans/${encodeURIComponent(p.slug)}`}
              className="block px-4 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-900"
            >
              <div className="flex items-center gap-2 mb-1">
                {p.status && <Badge variant="status">{p.status}</Badge>}
                <span className="font-medium">{p.title ?? p.slug}</span>
              </div>
              <div className="text-xs text-zinc-500 font-mono">{p.path}</div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
