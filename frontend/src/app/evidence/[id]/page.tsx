"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ShieldCheck, ShieldAlert, ArrowRightLeft } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { Button, Card, CardBody, CardHeader, CardTitle, Badge } from "@/components/ui";
import { CaseTimeline, type TimelineEvent } from "@/components/cases/case-timeline";
import { api } from "@/lib/api";
import { EvidenceRead, EvidenceTransferRead, IntegrityVerificationResult } from "@/types/evidence";
import { titleCase, formatDate } from "@/lib/utils";

export default function EvidenceDetailPage() {
  const params = useParams<{ id: string }>();
  const evidenceId = params?.id as string;

  const [evidence, setEvidence] = useState<EvidenceRead | null>(null);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [integrity, setIntegrity] = useState<IntegrityVerificationResult | null>(null);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);

  useEffect(() => {
    Promise.all([
      api.getEvidence(evidenceId),
      api.getEvidenceTimeline(evidenceId)
    ])
      .then(([ev, tr]) => {
        setEvidence(ev);
        setEvents(tr.items);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [evidenceId]);

  const handleVerify = async () => {
    setVerifying(true);
    try {
      const res = await api.verifyEvidence(evidenceId);
      setIntegrity(res);
    } catch (e: any) {
      alert("Verification failed: " + e.message);
    } finally {
      setVerifying(false);
    }
  };

  if (loading) return <AppShell><div className="p-4">Loading evidence...</div></AppShell>;
  if (error || !evidence) return <AppShell><div className="p-4 text-danger">{error || "Evidence not found"}</div></AppShell>;

  return (
    <AppShell>
      <div className="mb-6 flex items-center gap-4">
        <Link
          href={`/cases/${evidence.case_id}`}
          className="rounded-md p-2 text-muted hover:bg-elevated hover:text-ink"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-semibold text-ink">{evidence.evidence_number}</h1>
          <p className="text-sm text-muted">Evidence from case</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Evidence Details</CardTitle>
            </CardHeader>
            <CardBody className="space-y-4">
              <div>
                <div className="text-xs text-muted">Title</div>
                <div className="text-sm font-medium">{evidence.title}</div>
              </div>
              {evidence.description && (
                <div>
                  <div className="text-xs text-muted">Description</div>
                  <div className="text-sm">{evidence.description}</div>
                </div>
              )}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-muted">Type</div>
                  <div className="text-sm">{titleCase(evidence.evidence_type)}</div>
                </div>
                <div>
                  <div className="text-xs text-muted">Status</div>
                  <Badge tone="neutral">{evidence.status}</Badge>
                </div>
                <div>
                  <div className="text-xs text-muted">Collected By</div>
                  <div className="text-sm">{evidence.collector?.full_name || evidence.collector?.username || "N/A"}</div>
                </div>
                <div>
                  <div className="text-xs text-muted">Collected At</div>
                  <div className="text-sm">{evidence.collected_at ? formatDate(evidence.collected_at) : "N/A"}</div>
                </div>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader className="flex items-center justify-between">
              <CardTitle>Integrity & Source Document</CardTitle>
              {evidence.source_document_id && (
                <Button variant="secondary" size="sm" onClick={handleVerify} disabled={verifying}>
                  {verifying ? "Verifying..." : "Verify Hash"}
                </Button>
              )}
            </CardHeader>
            <CardBody className="space-y-4">
              {evidence.source_document_id ? (
                <>
                  <div>
                    <div className="text-xs text-muted">Source Document</div>
                    <div className="text-sm font-medium">{evidence.source_document?.title || "Unknown"}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted">SHA-256 Hash</div>
                    <div className="break-all font-mono text-xs text-muted">{evidence.sha256_hash}</div>
                  </div>
                  {integrity && (
                    <div className={`mt-4 rounded-md p-3 text-sm ${integrity.is_intact ? "bg-ok/10 text-ok" : "bg-danger/10 text-danger"}`}>
                      <div className="font-semibold flex items-center gap-2">
                        {integrity.is_intact ? <ShieldCheck className="w-4 h-4" /> : <ShieldAlert className="w-4 h-4" />}
                        {integrity.is_intact ? "Verification Passed" : "Verification Failed"}
                      </div>
                      <div className="mt-1">Expected: <span className="font-mono text-xs">{integrity.expected_hash}</span></div>
                      <div className="mt-1">Computed: <span className="font-mono text-xs">{integrity.actual_hash}</span></div>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-sm text-muted">No digital file attached to this evidence.</div>
              )}
            </CardBody>
          </Card>
          
          <Card>
            <CardHeader>
              <CardTitle>Full History & Custody</CardTitle>
            </CardHeader>
            <CaseTimeline events={events} />
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Current Custodian</CardTitle>
            </CardHeader>
            <CardBody>
              <div className="text-sm font-medium">
                {evidence.custodian?.full_name || evidence.custodian?.username || "Unknown"}
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Actions</CardTitle>
            </CardHeader>
            <CardBody className="space-y-2">
              <Button variant="secondary" className="w-full justify-start">
                <ArrowRightLeft className="mr-2 h-4 w-4" /> Transfer Custody
              </Button>
              {/* Other actions based on status */}
            </CardBody>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
