"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, CheckCircle, ShieldAlert, Loader2, Database, FileKey, Link as LinkIcon, AlertTriangle } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { Badge, Button, Card, CardBody, CardHeader, CardTitle } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { getCachedUser } from "@/lib/auth";
import type { DocumentDetail, VerifyChainResult } from "@/types";

export default function IntegrityCenterPage() {
  const params = useParams();
  const documentId = params?.id as string;

  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [result, setResult] = useState<VerifyChainResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tamperLoading, setTamperLoading] = useState(false);

  const user = getCachedUser();
  const allowDemoTamper = process.env.NEXT_PUBLIC_ALLOW_DEMO_TAMPER === "true";
  const canTamper = allowDemoTamper && (user?.role.name === "ADMIN" || user?.role.name === "INVESTIGATOR");

  const load = useCallback(async () => {
    if (!documentId) return;
    try {
      setLoading(true);
      const doc = await api.getDocument(documentId);
      setDocument(doc);
      
      const verification = await api.verifyChain(documentId, doc.current_version);
      setResult(verification);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load integrity data.");
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleTamper() {
    if (!document) return;
    try {
      setTamperLoading(true);
      await api.demoTamper(documentId, document.current_version);
      await load(); // re-run verification
    } catch (err) {
      alert(err instanceof Error ? err.message : "Tamper failed");
    } finally {
      setTamperLoading(false);
    }
  }

  if (loading) {
    return (
      <AppShell>
        <div className="flex h-[50vh] items-center justify-center text-muted">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          Loading Integrity Center...
        </div>
      </AppShell>
    );
  }

  if (error || !document) {
    return (
      <AppShell>
        <div className="p-8 text-center text-danger">{error || "Document not found"}</div>
      </AppShell>
    );
  }

  const currentVersion = document.versions.find((v) => v.version_number === document.current_version);
  if (!currentVersion) return null;

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl pb-12 pt-8">
        <Link
          href={`/documents/${documentId}`}
          className="mb-6 inline-flex items-center text-sm text-muted hover:text-foreground"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Document
        </Link>

        <h1 className="mb-2 text-2xl font-semibold tracking-tight">Integrity Center</h1>
        <p className="mb-8 text-sm text-muted">
          SHA-256 and the blockchain anchor let you detect unauthorized modification, not prevent it.
        </p>

        {/* Metadata */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Document Details</CardTitle>
          </CardHeader>
          <CardBody>
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 text-sm">
              <div>
                <dt className="text-muted">Name</dt>
                <dd className="font-medium">{document.title}</dd>
              </div>
              <div>
                <dt className="text-muted">Version</dt>
                <dd className="font-medium">v{currentVersion.version_number}</dd>
              </div>
              <div>
                <dt className="text-muted">Upload Date</dt>
                <dd className="font-medium">{new Date(currentVersion.created_at).toLocaleString()}</dd>
              </div>
              <div>
                <dt className="text-muted">Uploaded By</dt>
                <dd className="font-medium">{currentVersion.uploader.full_name || currentVersion.uploader.username}</dd>
              </div>
            </dl>
          </CardBody>
        </Card>

        {/* Verification Status Banner */}
        <div className="mb-6">
          {result?.status === "VERIFIED" && (
            <div className="rounded-lg border border-ok/20 bg-ok/5 p-6 text-center">
              <CheckCircle className="mx-auto mb-2 h-10 w-10 text-ok" />
              <h2 className="text-xl font-bold text-ok">VERIFIED</h2>
              <p className="text-sm text-muted mt-2">The current file matches the original hash perfectly.</p>
            </div>
          )}
          {result?.status === "MISMATCH" && (
            <div className="rounded-lg border border-danger/20 bg-danger/5 p-6 text-center">
              <ShieldAlert className="mx-auto mb-2 h-10 w-10 text-danger" />
              <h2 className="text-xl font-bold text-danger">INTEGRITY MISMATCH</h2>
              <p className="text-sm text-muted mt-2">The current file differs from the original hash. Tampering detected.</p>
            </div>
          )}
          {result?.status === "PENDING" && (
            <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-6 text-center">
              <Loader2 className="mx-auto mb-2 h-10 w-10 text-amber-500 animate-spin" />
              <h2 className="text-xl font-bold text-amber-500">PENDING ANCHOR</h2>
              <p className="text-sm text-muted mt-2">Document is verified locally but blockchain anchor is still processing.</p>
            </div>
          )}
          {result?.status === "UNAVAILABLE" && (
            <div className="rounded-lg border border-neutral/20 bg-neutral/5 p-6 text-center">
              <AlertTriangle className="mx-auto mb-2 h-10 w-10 text-neutral" />
              <h2 className="text-xl font-bold text-neutral">CHAIN UNAVAILABLE</h2>
              <p className="text-sm text-muted mt-2">Document is verified locally, but the blockchain network cannot be reached.</p>
            </div>
          )}
        </div>

        {/* Hashes */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Hash Verification Data</CardTitle>
          </CardHeader>
          <CardBody className="space-y-6">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Database className="h-4 w-4 text-muted" />
                <h3 className="text-sm font-medium">Stored hash</h3>
              </div>
              <p className="text-xs text-muted mb-1">From Postgres at upload time</p>
              <code className="block rounded bg-elevated p-3 text-xs text-ink break-all">
                {result?.stored_hash || "—"}
              </code>
            </div>

            <div>
              <div className="flex items-center gap-2 mb-1">
                <FileKey className="h-4 w-4 text-muted" />
                <h3 className="text-sm font-medium">Current hash</h3>
              </div>
              <p className="text-xs text-muted mb-1">Recomputed from the file right now</p>
              <code className={`block rounded bg-elevated p-3 text-xs break-all ${result?.computed_hash !== result?.stored_hash ? "text-danger font-bold" : "text-ink"}`}>
                {result?.computed_hash || "—"}
              </code>
            </div>

            <div>
              <div className="flex items-center gap-2 mb-1">
                <LinkIcon className="h-4 w-4 text-muted" />
                <h3 className="text-sm font-medium">Blockchain hash</h3>
              </div>
              <p className="text-xs text-muted mb-1">Read from the contract</p>
              <code className="block rounded bg-elevated p-3 text-xs text-ink break-all">
                {result?.on_chain_hash || "—"}
              </code>
            </div>
          </CardBody>
        </Card>

        {/* Tx Details */}
        {result?.tx_hash && (
          <Card className="mb-6 border-brand/20">
            <CardBody>
              <h3 className="text-sm font-medium mb-2 text-brand">Blockchain Transaction Details</h3>
              <div className="text-sm space-y-2">
                <div className="flex items-center gap-4">
                  <span className="text-muted w-24">Tx Hash:</span>
                  <code className="text-xs bg-elevated px-2 py-1 rounded">{result.tx_hash}</code>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-muted w-24">Block Number:</span>
                  <span className="text-ink font-mono">{result.block_number}</span>
                </div>
              </div>
            </CardBody>
          </Card>
        )}

        {/* Demo Tamper */}
        {canTamper && (
          <div className="mt-12 rounded-lg border-2 border-dashed border-danger/50 p-6">
            <h3 className="text-lg font-bold text-danger mb-2">Demo Mode: Tamper Simulation</h3>
            <p className="text-sm text-muted mb-4">
              This button deliberately rewrites a scratch copy of the current version&apos;s bytes in MinIO (never the real evidentiary object) to simulate a tamper event and prove the integrity detection works live.
            </p>
            <Button variant="danger" loading={tamperLoading} onClick={handleTamper}>
              Simulate File Tampering
            </Button>
          </div>
        )}
      </div>
    </AppShell>
  );
}
