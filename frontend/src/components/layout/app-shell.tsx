"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { 
  FolderKanban, 
  LayoutDashboard, 
  LogOut, 
  ScrollText, 
  Search,
  ShieldCheck,
  User as UserIcon,
  Building
} from "lucide-react";

import { Wordmark } from "@/components/brand";
import { Badge, Button, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { clearSession, getCachedUser, getToken } from "@/lib/auth";
import { cn, titleCase } from "@/lib/utils";
import type { User } from "@/types";

const NAV_GROUPS = [
  {
    title: "Overview",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    ]
  },
  {
    title: "Case Management",
    items: [
      { href: "/cases", label: "Cases", icon: FolderKanban },
      { href: "/search", label: "Global Search", icon: Search },
    ]
  },
  {
    title: "Audit & Compliance",
    roles: ["ADMIN", "AUDITOR"],
    items: [
      { href: "/audit", label: "Audit Trail", icon: ScrollText, roles: ["ADMIN", "AUDITOR"] },
    ]
  },
  {
    title: "Admin Console",
    roles: ["ADMIN"],
    items: [
      { href: "/admin/departments", label: "Departments", icon: Building },
      { href: "/admin/users", label: "Users", icon: UserIcon },
    ]
  }
];

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

  return (
    <div className="flex min-h-screen bg-bg">
      {/* --------------------------------------------------------- sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-line bg-surface lg:flex">
        <div className="border-b border-line px-6 py-5">
          <Wordmark showSubtitle={true} />
        </div>

        <nav className="flex-1 space-y-6 overflow-y-auto p-4">
          {NAV_GROUPS.map((group, i) => {
            if (group.roles && (!role || !group.roles.includes(role))) return null;
            
            const visibleItems = group.items.filter(item => !("roles" in item) || (role && (item as any).roles.includes(role)));
            if (visibleItems.length === 0) return null;

            return (
              <div key={i} className="space-y-1">
                <h4 className="px-3 pb-2 text-xs font-semibold tracking-wider text-muted uppercase">
                  {group.title}
                </h4>
                <div className="space-y-1">
                  {visibleItems.map((item) => {
                    const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                    const Icon = item.icon;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={cn(
                          "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                          active
                            ? "bg-brand/5 text-brand border-l-2 border-brand"
                            : "text-ink/70 hover:bg-elevated hover:text-ink border-l-2 border-transparent"
                        )}
                      >
                        <Icon className="h-4 w-4" />
                        {item.label}
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </nav>

        <div className="border-t border-line p-4">
          <div className="rounded-md border border-line bg-surface p-3 shadow-sm">
            {user ? (
              <>
                <div className="flex items-center gap-3 mb-3">
                  <div className="h-8 w-8 rounded-full bg-brand/10 flex items-center justify-center text-brand">
                    <UserIcon className="h-4 w-4" />
                  </div>
                  <div className="overflow-hidden">
                    <p className="truncate text-sm font-semibold text-ink">
                      {user.full_name || user.username}
                    </p>
                    <p className="truncate text-xs text-muted flex items-center gap-1 mt-0.5">
                      <Building className="h-3 w-3" />
                      {user.department?.name ?? "No department"}
                    </p>
                  </div>
                </div>
                <Badge tone="brand" className="w-full justify-center">
                  <ShieldCheck className="h-3 w-3 mr-1" />
                  {titleCase(user.role.name)}
                </Badge>
              </>
            ) : (
              <Skeleton className="h-16 w-full" />
            )}
          </div>
          <Button variant="ghost" size="sm" className="mt-3 w-full justify-center text-muted hover:text-ink" onClick={signOut}>
            <LogOut className="h-4 w-4 mr-2" />
            Sign out
          </Button>
        </div>
      </aside>

      {/* ----------------------------------------------------------- main */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* mobile bar */}
        <header className="flex items-center justify-between border-b border-line bg-surface px-4 py-3 lg:hidden">
          <Wordmark />
          <Button variant="ghost" size="icon" onClick={signOut} aria-label="Sign out">
            <LogOut className="h-5 w-5 text-muted" />
          </Button>
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-7xl p-6 md:p-8">
            {checking && !user ? (
              <div className="space-y-6">
                <Skeleton className="h-8 w-64" />
                <Skeleton className="h-32 w-full" />
                <Skeleton className="h-64 w-full" />
              </div>
            ) : (
              children
            )}
          </div>
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
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between border-b border-line pb-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-1.5 text-sm text-muted max-w-2xl">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
