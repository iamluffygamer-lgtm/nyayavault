"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { FolderKanban, LayoutDashboard, LogOut, ScrollText, ShieldCheck } from "lucide-react";

import { Wordmark } from "@/components/brand";
import { Badge, Button, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { clearSession, getCachedUser, getToken } from "@/lib/auth";
import { cn, titleCase } from "@/lib/utils";
import type { User } from "@/types";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/cases", label: "Cases", icon: FolderKanban },
  { href: "/audit", label: "Audit trail", icon: ScrollText, roles: ["ADMIN", "AUDITOR"] },
];

/**
 * Authenticated shell.
 *
 * The guard here is a convenience, not a security control: it decides what to
 * render, nothing more. Every request still carries a bearer token that the API
 * validates, and hiding a nav link never substitutes for the server-side
 * authorisation checks.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    setUser(getCachedUser());

    // Re-confirm the session against the API: a cached user object could be
    // stale, and only the server knows whether the account is still active.
    api
      .me()
      .then((fresh) => {
        setUser(fresh);
        setChecking(false);
      })
      .catch(() => setChecking(false));
  }, [router]);

  function signOut() {
    clearSession();
    router.replace("/login");
  }

  const role = user?.role?.name;
  const visibleNav = NAV.filter((item) => !item.roles || (role && item.roles.includes(role)));

  return (
    <div className="flex min-h-screen">
      {/* --------------------------------------------------------- sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-line bg-surface/50 lg:flex">
        <div className="border-b border-line px-5 py-4">
          <Wordmark />
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {visibleNav.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-brand/10 font-medium text-brand"
                    : "text-muted hover:bg-elevated hover:text-ink"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-line p-3">
          <div className="rounded-lg border border-line bg-elevated px-3 py-2.5">
            {user ? (
              <>
                <p className="truncate text-xs font-medium text-ink">
                  {user.full_name || user.username}
                </p>
                <p className="mt-0.5 truncate text-[11px] text-faint">
                  {user.department?.name ?? "No department"}
                </p>
                <Badge tone="brand" className="mt-2">
                  <ShieldCheck className="h-3 w-3" />
                  {titleCase(user.role.name)}
                </Badge>
              </>
            ) : (
              <Skeleton className="h-12 w-full" />
            )}
          </div>
          <Button variant="ghost" size="sm" className="mt-2 w-full justify-start" onClick={signOut}>
            <LogOut className="h-4 w-4" />
            Sign out
          </Button>
        </div>
      </aside>

      {/* ----------------------------------------------------------- main */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* mobile bar */}
        <header className="flex items-center justify-between border-b border-line bg-surface/50 px-4 py-3 lg:hidden">
          <Wordmark />
          <Button variant="ghost" size="icon" onClick={signOut} aria-label="Sign out">
            <LogOut className="h-4 w-4" />
          </Button>
        </header>
        <nav className="flex gap-1 border-b border-line px-3 py-2 lg:hidden">
          {visibleNav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs",
                pathname.startsWith(item.href)
                  ? "bg-brand/10 font-medium text-brand"
                  : "text-muted"
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <main className="flex-1 p-5 sm:p-7">
          {checking && !user ? (
            <div className="space-y-4">
              <Skeleton className="h-8 w-56" />
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-64 w-full" />
            </div>
          ) : (
            children
          )}
        </main>
      </div>
    </div>
  );
}

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-xs text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}
