"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";
import {
  BarChart3,
  DollarSign,
  FileText,
  HeartPulse,
  LogOut,
  Rss,
  Settings,
} from "lucide-react";

import { cn } from "@/lib/utils";

const NAV = [
  { href: "/admin/health", label: "Santé", icon: HeartPulse },
  { href: "/admin/articles", label: "Articles", icon: FileText },
  { href: "/admin/sources", label: "Sources", icon: Rss },
  { href: "/admin/costs", label: "Coûts IA", icon: DollarSign },
  { href: "/admin/ere", label: "ERE", icon: BarChart3 },
  { href: "/admin/settings", label: "Paramètres", icon: Settings },
] as const;

interface SidebarProps {
  userEmail: string;
  userName: string;
}

export function Sidebar({ userEmail, userName }: SidebarProps) {
  const pathname = usePathname();
  return (
    <aside className="sticky top-0 flex h-screen w-60 flex-col border-r border-[var(--color-border)] bg-white">
      <div className="px-6 pb-2 pt-6">
        <Link href="/admin" className="block">
          <p className="text-xs font-medium uppercase tracking-widest text-[var(--color-muted-foreground)]">
            DarijaAI
          </p>
          <p className="mt-1 text-lg font-semibold">Espace admin</p>
        </Link>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-[var(--color-primary)] text-white"
                  : "text-slate-700 hover:bg-slate-100",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-[var(--color-border)] p-4">
        <div className="mb-3 truncate">
          <p className="text-sm font-medium">{userName}</p>
          <p className="truncate text-xs text-[var(--color-muted-foreground)]">
            {userEmail}
          </p>
        </div>
        <button
          onClick={() => signOut({ redirectTo: "/login" })}
          className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-slate-700 transition-colors hover:bg-slate-100"
        >
          <LogOut className="h-4 w-4" />
          Déconnexion
        </button>
      </div>
    </aside>
  );
}
