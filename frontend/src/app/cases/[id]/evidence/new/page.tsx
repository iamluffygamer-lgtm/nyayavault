"use client";

import { useParams, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { AppShell } from "@/components/layout/app-shell";
import { Button, Card, CardBody, CardHeader, CardTitle, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { DocumentListItem } from "@/types";

export default function RegisterEvidencePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const caseId = params?.id as string;

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [evidenceType, setEvidenceType] = useState("PHYSICAL");
  const [sourceDocId, setSourceDocId] = useState<string>("");
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listDocuments(caseId).then(docs => {
      setDocuments(docs);
    }).catch(e => setError(e.message));
  }, [caseId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.createEvidence(caseId, {
        title,
        description,
        evidence_type: evidenceType,
        source_document_id: sourceDocId || undefined,
      });
      router.push(`/cases/${caseId}`);
    } catch (err: any) {
      setError(err.message);
      setSubmitting(false);
    }
  };

  return (
    <AppShell>
      <div className="mb-6 flex items-center gap-4">
        <Link
          href={`/cases/${caseId}`}
          className="rounded-md p-2 text-muted hover:bg-surface-hover hover:text-ink"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-semibold text-ink">Register Evidence</h1>
          <p className="text-sm text-muted">Add a new item to the chain of custody</p>
        </div>
      </div>

      <div className="mx-auto max-w-2xl">
        <Card>
          <CardBody>
            {error && <div className="mb-4 rounded bg-danger/10 p-3 text-sm text-danger">{error}</div>}
            
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium">Title *</label>
                <input
                  required
                  type="text"
                  className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  placeholder="e.g. Weapon found at scene"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium">Type *</label>
                <Select
                  value={evidenceType}
                  onChange={e => setEvidenceType(e.target.value)}
                >
                  <option value="PHYSICAL">Physical</option>
                  <option value="DIGITAL">Digital</option>
                  <option value="BIOLOGICAL">Biological</option>
                  <option value="DOCUMENTARY">Documentary</option>
                  <option value="OTHER">Other</option>
                </Select>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium">Description</label>
                <textarea
                  className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
                  rows={3}
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium">Source Document (Optional)</label>
                <Select
                  value={sourceDocId}
                  onChange={e => setSourceDocId(e.target.value)}
                >
                  <option value="">-- None --</option>
                  {documents.map(d => (
                    <option key={d.id} value={d.id}>{d.title}</option>
                  ))}
                </Select>
                <p className="mt-1 text-xs text-muted">Attach an existing case document to track its hash integrity in the custody chain.</p>
              </div>

              <div className="pt-4">
                <Button type="submit" variant="primary" disabled={submitting}>
                  {submitting ? "Registering..." : "Register Evidence"}
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>
      </div>
    </AppShell>
  );
}
