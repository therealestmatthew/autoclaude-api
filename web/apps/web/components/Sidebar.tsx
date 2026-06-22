"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Database,
  Inbox,
  Briefcase,
  BookOpen,
  ScrollText,
  Activity,
  ClipboardList,
  Wrench,
  CalendarRange,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/cn";
import navConfig from "@/nav.config.json";

type TabKey =
  | "dashboard"
  | "skills"
  | "timelines"
  | "engagements"
  | "catalog"
  | "queue"
  | "proposals"
  | "threads"
  | "conventions"
  | "plans";

const TAB_REGISTRY: Record<TabKey, { href: string; label: string; Icon: LucideIcon }> = {
  dashboard:   { href: "/dashboard",   label: "Dashboard",    Icon: LayoutDashboard },
  skills:      { href: "/skills",      label: "Skills & Tools", Icon: Wrench },
  timelines:   { href: "/timelines",   label: "Timelines",    Icon: CalendarRange },
  engagements: { href: "/engagements", label: "Engagements",  Icon: Briefcase },
  catalog:     { href: "/catalog",     label: "Catalog",      Icon: Database },
  queue:       { href: "/queue",       label: "Queue",        Icon: Inbox },
  proposals:   { href: "/proposals",   label: "Proposals",    Icon: ClipboardList },
  threads:     { href: "/threads",     label: "Threads",      Icon: Activity },
  conventions: { href: "/conventions", label: "Conventions",  Icon: BookOpen },
  plans:       { href: "/plans",       label: "Plans",        Icon: ScrollText },
};

// In static mode, hide tabs whose backing data isn't in the static bundle.
const STATIC_MODE = process.env.NEXT_PUBLIC_STATIC_MODE === "true";
const STATIC_HIDDEN: ReadonlySet<TabKey> = new Set<TabKey>([
  "queue",
  "proposals",
  "threads",
  "engagements",
  "timelines",
]);

const NAV = navConfig.tabs
  .filter((t) => t.enabled && t.key in TAB_REGISTRY)
  .filter((t) => !(STATIC_MODE && STATIC_HIDDEN.has(t.key as TabKey)))
  .map((t) => TAB_REGISTRY[t.key as TabKey]);

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden md:flex md:flex-col md:w-56 border-r border-zinc-200 dark:border-zinc-800 bg-white/60 dark:bg-zinc-950/60 backdrop-blur">
      <div className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-800">
        <Link href="/dashboard" className="block">
          <div className="text-xs uppercase tracking-widest text-zinc-500">
            FT-AutoClaude
          </div>
          <div className="text-base font-semibold mt-0.5">command center</div>
        </Link>
      </div>
      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {NAV.map(({ href, label, Icon }) => {
          const active = pathname === href || pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2 px-3 py-2 rounded-md text-sm",
                active
                  ? "bg-brand-50 text-brand-700 dark:bg-zinc-800 dark:text-zinc-50"
                  : "text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-900",
              )}
            >
              <Icon className="w-4 h-4" />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="px-5 py-4 border-t border-zinc-200 dark:border-zinc-800 text-xs text-zinc-500">
        Forge · Phase 10.1
      </div>
    </aside>
  );
}
