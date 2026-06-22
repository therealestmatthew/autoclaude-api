import { Suspense } from "react";
import { api } from "@/lib/api";
import { ApiBanner } from "@/components/ApiBanner";
import { CatalogBrowser } from "@/components/CatalogBrowser";

export default async function CatalogPage() {
  let list;
  try {
    list = await api.catalog.list({ limit: 5000 });
  } catch {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Catalog</h1>
        <ApiBanner />
      </div>
    );
  }

  return (
    <Suspense fallback={null}>
      <CatalogBrowser allItems={list.items} />
    </Suspense>
  );
}
