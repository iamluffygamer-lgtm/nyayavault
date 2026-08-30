"use client";

import { useCallback, useEffect, useState } from "react";
import { Link2, ShieldAlert, ShieldCheck } from "lucide-react";

import { AuditTimeline } from "@/components/audit/audit-timeline";
import { AppShell, PageHeader } from "@/components/layout/app-shell";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  Skeleton,
} from "@/components/ui";
import { api } from "@/lib/api";
import { shortHash } from "@/lib/utils";
import type { AuditEvent, ChainVerificationReport } from "@/types";

/** Oversight view. The API restricts this to ADMIN and AUDITOR. */
export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [chain, setChain] = useState<ChainVerificationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const page = await api.auditEvents(100);
      setEvents(page.items);
      setTotal(page.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the audit log.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function verify() {
    setChecking(true);
    try {
      setChain(await api.verifyAuditChain());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed.");
    } finally {
      setChecking(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        title="Audit trail"
        description={loading ? "Loading…" : `${total} recorded event(s), newest first`}
      />

      {error && (
        <div className="mb-4">
          <Alert tone="danger">{error}</Alert>
        </div>
      )}

      <Card className="mb-4">
        <CardBody className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-elevated text-brand">
              <Link2 className="h-4 w-4" />
            </span>
            <div>
              <p className="text-sm font-medium">Chain verification</p>
              <p className="mt-0.5 max-w-2xl text-xs leading-relaxed text-muted">
                Each event stores the hash of its predecessor. Verification walks those
                pointers from the genesis record and recomputes every hash, so an altered or
                deleted row is detectable even if it was changed directly in the database.
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
                      head {shortHash(chain.head_hash, 12)}
                    </span>
                  )}
                </div>
              )}
              {chain && <p className="mt-2 text-xs text-muted">{chain.detail}</p>}
            </div>
          </div>
          <Button variant="secondary" size="sm" loading={checking} onClick={verify}>
            Verify chain
          </Button>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>System-wide activity</CardTitle>
        </CardHeader>
        {loading ? (
          <CardBody className="space-y-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </CardBody>
        ) : (
          <AuditTimeline events={events} />
        )}
      </Card>
    </AppShell>
  );
}
