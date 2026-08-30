"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Download, FileText, ShieldCheck, Upload } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { IntegrityBadge, type IntegrityState } from "@/components/integrity-badge";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Table,
  Td,
  Th,
  Skeleton,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { formatBytes, formatDateTime, titleCase } from "@/lib/utils";
import type { DocumentDetail, IntegrityReport } from "@/types";

export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const documentId = params?.id as string;

  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [report, setReport] = useState<IntegrityReport | null>(null);
  const [state, setState] = useState<IntegrityState>("unknown");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // new-version form
  const [file, setFile] = useState<File | null>(null);
  const [reason, setReason] = useState("");
  const [versionError, setVersionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!documentId) return;
    setLoading(true);
    try {
      setDocument(await api.getDocument(documentId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load this document.");
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function verify() {
    setState("checking");
    try {
      const result = await api.verifyDocument(documentId);
      setReport(result);
      setState(result.verified ? "verified" : "failed");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed.");
      setState("unknown");
    }
  }

  async function download(versionNumber: number, filename: string) {
    setBusy(true);
    try {
      await api.downloadDocument(documentId, filename, versionNumber);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The download was refused.");
    } finally {
      setBusy(false);
    }
  }

  async function addVersion(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setVersionError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("change_reason", reason.trim());
      await api.uploadVersion(documentId, form);
      setFile(null);
      setReason("");
      setReport(null);
      setState("unknown");
      await load();
    } catch (err) {
      setVersionError(err instanceof ApiError ? err.message : "Could not add the version.");
    } finally {
      setBusy(false);
    }
  }

  const triggerOCR = async () => {
    if (!document) return;
    setBusy(true);
    try {
      await api.triggerOCR(document.id, document.current_version);
      alert("OCR process triggered in the background. It may take a few moments.");
    } catch (err) {
      alert("Failed to trigger OCR.");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <AppShell>
        <Skeleton className="h-6 w-64" />
        <Skeleton className="mt-3 h-28 w-full" />
        <Skeleton className="mt-4 h-64 w-full" />
      </AppShell>
    );
  }

  if (error || !document) {
    return (
      <AppShell>
        <Alert tone="danger">{error ?? "This document is not available."}</Alert>
      </AppShell>
    );
  }

  const current = document.versions.find((v) => v.version_number === document.current_version);
  const verificationFor = (versionNumber: number) =>
    report?.results.find((r) => r.version_number === versionNumber);

  return (
    <AppShell>
      <Link
        href={`/cases/${document.case_id}`}
        className="mb-4 inline-flex items-center gap-1.5 text-xs text-muted hover:text-ink"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back to case
      </Link>

      {/* ------------------------------------------------------- metadata */}
      <Card className="mb-4">
        <CardBody>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="neutral">{titleCase(document.document_type)}</Badge>
                <Badge tone="brand">v{document.current_version} current</Badge>
                <IntegrityBadge state={state} />
              </div>
              <h1 className="mt-2 flex items-center gap-2 text-lg font-semibold tracking-tight">
                <FileText className="h-4 w-4 text-brand" />
                {document.title}
              </h1>
              {document.description && (
                <p className="mt-2 max-w-3xl text-xs leading-relaxed text-muted">
                  {document.description}
                </p>
              )}
              <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-[11px] text-faint">
                <div>
                  <dt className="inline">Added by </dt>
                  <dd className="inline text-muted">
                    {document.creator.full_name || document.creator.username}
                  </dd>
                </div>
                <div>
                  <dt className="inline">First stored </dt>
                  <dd className="inline text-muted">{formatDateTime(document.created_at)}</dd>
                </div>
                <div>
                  <dt className="inline">Versions </dt>
                  <dd className="inline text-muted">{document.versions.length}</dd>
                </div>
              </dl>
            </div>

            <div className="flex gap-2">
              <Button variant="secondary" size="sm" loading={state === "checking"} onClick={verify}>
                <ShieldCheck className="h-4 w-4" />
                Verify integrity
              </Button>
              {current && (
                <>
                  <Button
                    size="sm"
                    variant="outline"
                    loading={busy}
                    onClick={triggerOCR}
                  >
                    <FileText className="h-4 w-4" />
                    Extract Text (OCR)
                  </Button>
                  <Button
                    size="sm"
                    loading={busy}
                    onClick={() => void download(current.version_number, current.original_filename)}
                  >
                    <Download className="h-4 w-4" />
                    Download
                  </Button>
                </>
              )}
            </div>
          </div>

          {report && (
            <div className="mt-4">
              <Alert tone={report.verified ? "ok" : "danger"}>
                {report.verified
                  ? `All ${report.results.length} stored version(s) re-hashed to exactly the value recorded at upload (${report.algorithm}).`
                  : `Integrity check FAILED. ${report.results
                      .filter((r) => !r.verified)
                      .map((r) => `v${r.version_number}: ${r.detail}`)
                      .join(" ")}`}
              </Alert>
            </div>
          )}
        </CardBody>
      </Card>

      {/* -------------------------------------------------- extracted text */}
      {current && current.text && (
        <Card className="mb-4">
          <CardHeader>
            <CardTitle className="flex justify-between">
              <span>Extracted Text</span>
              <Badge tone={current.text.extraction_status === "COMPLETED" ? "ok" : "neutral"}>
                {current.text.extraction_status} ({current.text.extraction_method || "N/A"})
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardBody>
            {current.text.extracted_text ? (
              <pre className="text-[11px] leading-relaxed whitespace-pre-wrap bg-subtle p-4 rounded-md border border-subtle overflow-auto max-h-96 text-ink">
                {current.text.extracted_text}
              </pre>
            ) : (
              <p className="text-sm text-muted italic">No text extracted.</p>
            )}
          </CardBody>
        </Card>
      )}

      {/* -------------------------------------------------- version history */}
      <Card className="mb-4">
        <CardHeader>
          <CardTitle>Version history</CardTitle>
          <p className="mt-0.5 text-[11px] text-muted">
            Versions are append-only. Uploading a revision adds a new row; nothing above it changes.
          </p>
        </CardHeader>
        <Table>
          <thead>
            <tr>
              <Th>Ver.</Th>
              <Th>File</Th>
              <Th>SHA-256</Th>
              <Th>Size</Th>
              <Th>Uploaded by</Th>
              <Th>Reason</Th>
              <Th />
            </tr>
          </thead>
          <tbody>
            {document.versions.map((version) => {
              const check = verificationFor(version.version_number);
              return (
                <tr key={version.id} className="hover:bg-elevated/60">
                  <Td>
                    <Badge tone={version.version_number === document.current_version ? "brand" : "neutral"}>
                      v{version.version_number}
                    </Badge>
                  </Td>
                  <Td className="max-w-[12rem] truncate text-xs">{version.original_filename}</Td>
                  <Td>
                    {/* Shown in full: an officer may need to read it aloud or
                        compare it against a hash computed elsewhere. */}
                    <span className="hash block max-w-[15rem] text-faint">
                      {version.sha256_hash}
                    </span>
                    {check && (
                      <span
                        className={`mt-1 block text-[11px] ${check.verified ? "text-ok" : "text-danger"}`}
                      >
                        {check.verified ? "matches stored bytes" : "MISMATCH"}
                      </span>
                    )}
                  </Td>
                  <Td className="whitespace-nowrap text-xs text-muted">
                    {formatBytes(version.file_size)}
                  </Td>
                  <Td className="whitespace-nowrap text-xs">
                    <span className="block">
                      {version.uploader.full_name || version.uploader.username}
                    </span>
                    <span className="text-[11px] text-faint">
                      {formatDateTime(version.created_at)}
                    </span>
                  </Td>
                  <Td className="max-w-[14rem] text-xs text-muted">
                    {version.change_reason ?? "—"}
                  </Td>
                  <Td>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        void download(version.version_number, version.original_filename)
                      }
                    >
                      <Download className="h-3.5 w-3.5" />
                    </Button>
                  </Td>
                </tr>
              );
            })}
          </tbody>
        </Table>
      </Card>

      {/* ------------------------------------------------------ new version */}
      <Card>
        <CardHeader className="flex items-center gap-2">
          <Upload className="h-4 w-4 text-brand" />
          <CardTitle>Supersede with a new version</CardTitle>
        </CardHeader>
        <CardBody>
          <form onSubmit={addVersion} className="space-y-3">
            {versionError && <Alert tone="danger">{versionError}</Alert>}
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="version-file">Replacement file</Label>
                <Input
                  id="version-file"
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.txt,.docx,.doc"
                  className="h-auto py-1.5 text-xs file:mr-3 file:rounded file:border-0 file:bg-elevated file:px-2 file:py-1 file:text-xs file:text-ink"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                  required
                />
              </div>
              <div>
                <Label htmlFor="version-reason">Reason for the change (required)</Label>
                <Input
                  id="version-reason"
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="e.g. Corrected witness name on page 3"
                  minLength={3}
                  maxLength={512}
                  required
                />
              </div>
            </div>
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] leading-relaxed text-faint">
                The current version stays exactly as it is. A reason is mandatory because a
                revision to case material has to be explainable later.
              </p>
              <Button
                type="submit"
                size="sm"
                loading={busy}
                disabled={!file || reason.trim().length < 3}
              >
                Add version {document.current_version + 1}
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>
    </AppShell>
  );
}
