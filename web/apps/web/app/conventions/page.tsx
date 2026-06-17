import Link from "next/link";
import { api } from "@/lib/api";
import { ApiBanner } from "@/components/ApiBanner";

export const dynamic = "force-dynamic";

export default async function ConventionsPage() {
  let list;
  try {
    list = await api.conventions.list();
  } catch {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Conventions</h1>
        <ApiBanner />
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Conventions</h1>
        <p className="text-sm text-zinc-500 mt-1">
          The rules that govern how content lives in this repo.
        </p>
      </header>
      <ul className="space-y-1">
        {list.items.map((c) => (
          <li key={c.path}>
            <Link
              href={`/conventions/${encodeURIComponent(c.slug)}`}
              className="block px-3 py-2 rounded hover:bg-zinc-100 dark:hover:bg-zinc-900"
            >
              <div className="font-medium">{c.title ?? c.slug}</div>
              <div className="text-xs text-zinc-500 font-mono">{c.path}</div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
