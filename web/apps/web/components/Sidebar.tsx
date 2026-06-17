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
} from "lucide-react";
import { cn } from "@/lib/cn";

const NAV = [
  { href: "/dashboard", label: "Dashboard", Icon: LayoutDashboard },
  { href: "/catalog", label: "Catalog", Icon: Database },
  { href: "/queue", label: "Queue", Icon: Inbox },
  { href: "/threads", label: "Threads", Icon: Activity },
  { href: "/engagements", label: "Engagements", Icon: Briefcase },
  { href: "/conventions", label: "Conventions", Icon: BookOpen },
  { href: "/plans", label: "Plans", Icon: ScrollText },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden md:flex md:flex-col md:w-56 border-r border-zinc-200 dark:border-zinc-800 bg-white/60 dark:bg-zinc-950/60 backdrop-blur">
      <div className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-800">
        <Link href="/dashboard" className="block">
          <div className="text-xs uppercase tracking-widest text-zinc-500">
            autoclaude
          </div>
          <div className="text-base font-semibold mt-0.5">command center</div>
        </Link>
      </div>
      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {NAV.map(({ href, label, Icon }) => {
          const active =
            pathname === href || (href !== "/" && pathname.startsWith(href));
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
        Phase 8.1 · read-only
      </div>
    </aside>
  );
}
