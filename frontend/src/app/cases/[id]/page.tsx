"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Lock, Key, FileText, Hash, ShieldCheck, Upload, Users } from "lucide-react";

import { CaseTimeline, type TimelineEvent } from "@/components/cases/case-timeline";
import { CaseStatusBadge } from "@/components/cases/case-status-badge";
import { DocumentUpload } from "@/components/documents/document-upload";
import { EvidenceList } from "@/components/evidence/evidence-list";
import { CourtAccessModal } from "@/components/cases/court-access-modal";
import { AppShell } from "@/components/layout/app-shell";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  EmptyState,
  Select,
  Skeleton,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { api, request } from "@/lib/api";
import { formatBytes, formatDate, relativeTime, shortHash, titleCase } from "@/lib/utils";
import type {
  AuditEvent,
  CaseAssignment,
  CaseDetail,
  CaseStatus,
  DocumentListItem,
} from "@/types";

const STATUSES: CaseStatus[] = [
  "OPEN",
  "UNDER_INVESTIGATION",
  "SUBMITTED",
  "CLOSED",
  "ARCHIVED",
];

export default function CaseDetailPage() {
  const params = useParams<{ id: string }>();
  const caseId = params?.id as string;

  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [members, setMembers] = useState<CaseAssignment[]>([]);
  const [tab, setTab] = useState<"documents" | "evidence" | "activity" | "members">("documents");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusSaving, setStatusSaving] = useState(false);

  const load = useCallback(async () => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    try {
      const [caseDetail, docs, audit, assigned] = await Promise.all([
        api.getCase(caseId),
        api.listDocuments(caseId),
        api.getCaseTimeline(caseId, 50),
        api.listCaseMembers(caseId).catch(() => [] as CaseAssignment[]),
      ]);
      setDetail(caseDetail);
      setDocuments(docs);
      setEvents(audit.items);
      setMembers(assigned);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load this case.");
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function changeStatus(next: CaseStatus) {
    if (!detail) return;
    setStatusSaving(true);
    try {
      const updated = await api.updateCaseStatus(detail.id, next);
      setDetail({ ...detail, status: updated.status, updated_at: updated.updated_at });
      void load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change the status.");
    } finally {
      setStatusSaving(false);
    }
  }

  if (loading) {
    return (
      <AppShell>
        <Skeleton className="h-6 w-64" />
        <Skeleton className="mt-3 h-24 w-full" />
        <Skeleton className="mt-4 h-72 w-full" />
    </AppShell>
    );
  }

  if (error || !detail) {
    return (
      <AppShell>
        <Link href="/cases" className="mb-4 inline-flex items-center gap-1.5 text-xs text-muted hover:text-ink">
          <ArrowLeft className="h-3.5 w-3.5" /> Back to cases
        </Link>
        <Alert tone="danger">
          {error ?? "This case is not available."} If you believe you should have access,
          ask the case owner to assign you.
        </Alert>
    </AppShell>
    );
  }

  const canManage = detail.access_level === "MANAGE";

  const [courtModalOpen, setCourtModalOpen] = useState(false);
  const [isLocking, setIsLocking] = useState(false);

  async function handleLockForCourt() {
    if (!confirm("Are you sure you want to lock this case for court? No further evidence can be transferred or documents added.")) return;
    setIsLocking(true);
    try {
      await request(`/cases/${detail?.id}/lock-for-court`, { method: "POST" });
      load();
    } catch (e: any) {
      alert(e.message || "Failed to lock case.");
    } finally {
      setIsLocking(false);
    }
  }


  return (
    <AppShell>
      <Link
        href="/cases"
        className="mb-4 inline-flex items-center gap-1.5 text-xs text-muted hover:text-ink"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back to cases
      </Link>

      {/* ------------------------------------------------------ case header */}
      <Card className="mb-4">
        <CardBody>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs text-brand">{detail.case_number}</span>
                <CaseStatusBadge status={detail.status} />
                {detail.access_level && (
                  <Badge tone="neutral">{titleCase(detail.access_level)} access</Badge>
                )}
              </div>
              <h1 className="mt-2 text-lg font-semibold tracking-tight">{detail.title}</h1>
              {detail.description && (
                <p className="mt-2 max-w-3xl whitespace-pre-line text-xs leading-relaxed text-muted">
                  {detail.description}
                </p>
              )}
              <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-[11px] text-faint">
                <div>
                  <dt className="inline">Opened by </dt>
                  <dd className="inline text-muted">
                    {detail.creator.full_name || detail.creator.username}
                  </dd>
                </div>
                <div>
                  <dt className="inline">Opened </dt>
                  <dd className="inline text-muted">{formatDate(detail.created_at)}</dd>
                </div>
                <div>
                  <dt className="inline">Documents </dt>
                  <dd className="inline text-muted">{documents.length}</dd>
                </div>
              </dl>
            </div>

            {canManage && (
              <div className="w-48">
                <label htmlFor="case-status" className="mb-1.5 block text-[11px] text-faint">
                  Change status
                </label>
                <Select
                  id="case-status"
                  value={detail.status}
                  disabled={statusSaving || detail.status === "ARCHIVED"}
                  onChange={(event) => void changeStatus(event.target.value as CaseStatus)}
                >
                  {STATUSES.map((value) => (
                    <option key={value} value={value}>
                      {titleCase(value)}
                    </option>
                  ))}
                </Select>

                {detail.status === "ARCHIVED" && (
                  <p className="mt-1 text-[11px] text-faint">Archived cases are read-only.</p>
                )}

              </div>
            )}


          </div>
        </CardBody>
      </Card>


      {canManage && (detail.status === "SUBMITTED" || detail.status === "UNDER_TRIAL") && (
        <Card className="mb-4 border-brand bg-brand/5">
          <CardBody className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-brand">Court Portal Actions</h3>
              <p className="text-xs text-muted mt-1">This case is currently {detail.status}. Use the actions here to lock the case and generate an access code for the court.</p>
            </div>
            <div className="flex gap-3">
              {detail.status === "SUBMITTED" && (
                <Button variant="outline" className="border-brand text-brand hover:bg-brand/10" onClick={handleLockForCourt} loading={isLocking}>
                  <Lock className="mr-2 h-4 w-4" />
                  Lock & Submit for Court
                </Button>
              )}
              {detail.status === "UNDER_TRIAL" && (
                <Button variant="primary" onClick={() => setCourtModalOpen(true)}>
                  <Key className="mr-2 h-4 w-4" />
                  Generate Court Access Code
                </Button>
              )}
            </div>
          </CardBody>
        </Card>
      )}

      {/* ------------------------------------------------------------- tabs */}
      <div className="mb-4 flex gap-1 border-b border-line">
        {(
          [
            ["documents", `Documents (${documents.length})`],
            ["evidence", "Evidence"],
            ["activity", `Activity (${events.length})`],
            ["members", `Members (${members.length})`],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 px-3 py-2 text-xs transition-colors ${
              tab === key
                ? "border-brand font-medium text-brand"
                : "border-transparent text-muted hover:text-ink"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "documents" && (
        <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
          <Card>
            <CardHeader>
              <CardTitle>Documents</CardTitle>
            </CardHeader>
            {documents.length === 0 ? (
              <EmptyState
                icon={<FileText className="h-6 w-6" />}
                title="No documents in this case"
                description={
                  detail.can_upload
                    ? "Upload the first document. It will be hashed on receipt and stored as version 1."
                    : "Documents added to this case will be listed here."
                }
              />
            ) : (
              <Table>
                <thead>
                  <tr>
                    <Th>Title</Th>
                    <Th>Type</Th>
                    <Th>Ver.</Th>
                    <Th>SHA-256</Th>
                    <Th>Size</Th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr key={doc.id} className="hover:bg-elevated/60">
                      <Td className="max-w-[15rem]">
                        <Link
                          href={`/documents/${doc.id}`}
                          className="block truncate hover:underline"
                        >
                          {doc.title}
                        </Link>
                        <span className="mt-0.5 block truncate text-[11px] text-faint">
                          {doc.latest_filename}
                        </span>
                      </Td>
                      <Td className="whitespace-nowrap text-xs text-muted">
                        {titleCase(doc.document_type)}
                      </Td>
                      <Td>
                        <Badge tone="neutral">v{doc.current_version}</Badge>
                      </Td>
                      <Td>
                        <span
                          className="hash text-faint"
                          title={doc.latest_sha256 ?? undefined}
                        >
                          {shortHash(doc.latest_sha256, 10)}
                        </span>
                      </Td>
                      <Td className="whitespace-nowrap text-xs text-muted">
                        {formatBytes(doc.latest_file_size)}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Card>

          <Card className="self-start">
            <CardHeader className="flex items-center gap-2">
              <Upload className="h-4 w-4 text-brand" />
              <CardTitle>Upload a document</CardTitle>
            </CardHeader>
            {detail.can_upload ? (
              <DocumentUpload caseId={detail.id} onUploaded={() => void load()} />
            ) : (
              <CardBody>
                <Alert tone="info">
                  You have read-only access to this case, so uploads are disabled.
                  {detail.status === "CLOSED" || detail.status === "ARCHIVED"
                    ? " The case is also closed to further changes."
                    : ""}
                </Alert>
              </CardBody>
            )}
          </Card>
        </div>
      )}

      {tab === "evidence" && (
        <EvidenceList caseId={caseId} />
      )}

      {tab === "activity" && (
        <Card>
          <CardHeader className="flex items-center gap-2">
            <Hash className="h-4 w-4 text-brand" />
            <div>
              <CardTitle>Case audit trail</CardTitle>
              <p className="mt-0.5 text-[11px] text-muted">
                Newest first. Each entry is a link in the system-wide hash chain.
              </p>
            </div>
          </CardHeader>
          <CaseTimeline events={events} />
        </Card>
      )}

      {tab === "members" && (
        <Card>
          <CardHeader className="flex items-center gap-2">
            <Users className="h-4 w-4 text-brand" />
            <CardTitle>Case members</CardTitle>
          </CardHeader>
          {members.length === 0 ? (
            <EmptyState
              title="No explicit members"
              description="Only the case owner, administrators and auditors can currently reach this case."
            />
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Officer</Th>
                  <Th>Role</Th>
                  <Th>Case access</Th>
                  <Th>Assigned</Th>
                </tr>
              </thead>
              <tbody>
                {members.map((member) => (
                  <tr key={member.id}>
                    <Td>
                      <span className="block">{member.user.full_name || member.user.username}</span>
                      <span className="text-[11px] text-faint">
                        {member.user.department?.name ?? "No department"}
                      </span>
                    </Td>
                    <Td>
                      <Badge tone="neutral">
                        <ShieldCheck className="h-3 w-3" />
                        {titleCase(member.user.role.name)}
                      </Badge>
                    </Td>
                    <Td>
                      <Badge tone="brand">{titleCase(member.access_level)}</Badge>
                    </Td>
                    <Td className="whitespace-nowrap text-xs text-muted">
                      {relativeTime(member.created_at)}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      )}
      {detail && <CourtAccessModal open={courtModalOpen} onClose={() => setCourtModalOpen(false)} caseId={detail.id} />}
    </AppShell>
  );
}
