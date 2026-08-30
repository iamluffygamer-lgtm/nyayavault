"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  FileText,
  FolderKanban,
  Link2,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";

import { AuditTimeline } from "@/components/audit/audit-timeline";
import { CaseStatusBadge } from "@/components/cases/case-status-badge";
import { AppShell, PageHeader } from "@/components/layout/app-shell";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  EmptyState,
  Skeleton,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { api } from "@/lib/api";
import { getCachedUser } from "@/lib/auth";
import { formatDate, shortHash } from "@/lib/utils";
import type {
  AuditEvent,
  CaseStatistics,
  CaseSummary,
  ChainVerificationReport,
} from "@/types";

function StatTile({
  label,
  value,
  icon,
  loading,
}: {
  label: string;
  value: number | undefined;
  icon: React.ReactNode;
  loading: boolean;
}) {
  return (
    <Card>
      <CardBody className="flex items-center gap-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-elevated text-brand">
          {icon}
        </span>
        <div className="min-w-0">
          <p className="text-[11px] uppercase tracking-wide text-faint">{label}</p>
          {loading ? (
            <Skeleton className="mt-1 h-6 w-10" />
          ) : (
            // Real counts from the API. When the database is empty this is a
            // genuine zero, never a placeholder figure.
            <p className="text-xl font-semibold tabular-nums">{value ?? 0}</p>
          )}
        </div>
      </CardBody>
    </Card>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<CaseStatistics | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [chain, setChain] = useState<ChainVerificationReport | null>(null);
  const [chainChecking, setChainChecking] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isOversight = ["ADMIN", "AUDITOR"].includes(getCachedUser()?.role?.name ?? "");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statistics, caseList] = await Promise.all([api.statistics(), api.listCases({ limit: 5 })]);
      setStats(statistics);
      setCases(caseList.items);

      // Recent activity: oversight roles see the system-wide log; everyone else
      // sees the trail of their most recent case.
      if (isOversight) {
        setEvents((await api.auditEvents(12)).items);
      } else if (caseList.items.length > 0) {
        setEvents((await api.caseAudit(caseList.items[0].id, 12)).items);
      } else {
        setEvents([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the dashboard.");
    } finally {
      setLoading(false);
    }
  }, [isOversight]);

  useEffect(() => {
    void load();
  }, [load]);

  async function verifyChain() {
    setChainChecking(true);
    try {
      setChain(await api.verifyAuditChain());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chain verification failed.");
    } finally {
      setChainChecking(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        title="Dashboard"
        description="Live counts across the cases you are authorised to see."
        action={
          <Button variant="secondary" size="sm" onClick={() => void load()}>
            Refresh
          </Button>
        }
      />

      {error && (
        <div className="mb-4">
          <Alert tone="danger">{error}</Alert>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Active cases"
          value={stats?.active_cases}
          icon={<FolderKanban className="h-4 w-4" />}
          loading={loading}
        />
        <StatTile
          label="Total cases"
          value={stats?.total_cases}
          icon={<Activity className="h-4 w-4" />}
          loading={loading}
        />
        <StatTile
          label="Documents"
          value={stats?.total_documents}
          icon={<FileText className="h-4 w-4" />}
          loading={loading}
        />
        <StatTile
          label="Closed cases"
          value={stats?.closed_cases}
          icon={<ShieldCheck className="h-4 w-4" />}
          loading={loading}
        />
      </div>

      {/* ------------------------------------------------- audit chain panel */}
      {isOversight && (
        <Card className="mt-4">
          <CardBody className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-elevated text-brand">
                <Link2 className="h-4 w-4" />
              </span>
              <div>
                <p className="text-sm font-medium">Audit chain integrity</p>
                <p className="mt-0.5 max-w-xl text-xs text-muted">
                  Recomputes every event hash and confirms each links to the one before it.
                  A silent edit or deletion anywhere in the log breaks the chain here.
                </p>
                {chain && (
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {chain.intact ? (
                      <Badge tone="ok">
                        <ShieldCheck className="h-3 w-3" /> Intact
                      </Badge>
                    ) : (
                      <Badge tone="danger">
                        <ShieldAlert className="h-3 w-3" /> Broken
                      </Badge>
                    )}
                    <span className="text-[11px] text-muted">
                      {chain.events_checked} event(s) checked
                    </span>
                    {chain.head_hash && (
                      <span className="hash text-faint" title={chain.head_hash}>
                        head {shortHash(chain.head_hash, 10)}
                      </span>
                    )}
                  </div>
                )}
                {chain && !chain.intact && (
                  <p className="mt-2 text-xs text-danger">{chain.detail}</p>
                )}
              </div>
            </div>
            <Button variant="secondary" size="sm" loading={chainChecking} onClick={verifyChain}>
              Verify chain
            </Button>
          </CardBody>
        </Card>
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.35fr_1fr]">
        {/* ------------------------------------------------------ recent cases */}
        <Card>
          <CardHeader className="flex items-center justify-between">
            <CardTitle>Recent cases</CardTitle>
            <Link href="/cases" className="text-xs text-brand hover:underline">
              View all
            </Link>
          </CardHeader>

          {loading ? (
            <CardBody className="space-y-2">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
            </CardBody>
          ) : cases.length === 0 ? (
            <EmptyState
              icon={<FolderKanban className="h-6 w-6" />}
              title="No cases yet"
              description="Cases you open or are assigned to will appear here."
              action={
                <Link href="/cases">
                  <Button size="sm">Go to cases</Button>
                </Link>
              }
            />
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Case number</Th>
                  <Th>Title</Th>
                  <Th>Status</Th>
                  <Th>Opened</Th>
                </tr>
              </thead>
              <tbody>
                {cases.map((item) => (
                  <tr key={item.id} className="hover:bg-elevated/60">
                    <Td>
                      <Link
                        href={`/cases/${item.id}`}
                        className="font-mono text-xs text-brand hover:underline"
                      >
                        {item.case_number}
                      </Link>
                    </Td>
                    <Td className="max-w-[18rem] truncate">{item.title}</Td>
                    <Td>
                      <CaseStatusBadge status={item.status} />
                    </Td>
                    <Td className="whitespace-nowrap text-xs text-muted">
                      {formatDate(item.created_at)}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>

        {/* --------------------------------------------------- recent activity */}
        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
          </CardHeader>
          {loading ? (
            <CardBody className="space-y-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </CardBody>
          ) : (
            <div className="max-h-[26rem] overflow-y-auto">
              <AuditTimeline events={events} />
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
