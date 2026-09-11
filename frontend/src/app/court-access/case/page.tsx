"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { courtRequest } from "@/lib/court-api";
import { Button } from "@/components/ui";
import { Alert } from "@/components/ui";
import { CaseStatusBadge } from "@/components/cases/case-status-badge";
import { ArrowLeft, LogOut, CheckCircle, FileText, Database } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui";

export default function CourtCaseView() {
  const router = useRouter();
  const [caseDetail, setCaseDetail] = useState<any>(null);
  const [docs, setDocs] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [c, d] = await Promise.all([
          courtRequest<any>("/court/case"),
          courtRequest<any[]>("/court/documents")
        ]);
        setCaseDetail(c);
        setDocs(d);
      } catch (e: any) {
        setError(e.message || "Failed to load case.");
      }
    }
    load();
  }, []);


  async function downloadDoc(docId: string, version: number) {
    try {
      const token = sessionStorage.getItem("court_token");
      const response = await fetch(`/api/v1/court/documents/${docId}/download?version=${version}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!response.ok) throw new Error("Download refused");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `doc-${docId}-v${version}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      alert("Failed to download document.");
    }
  }

  async function endSession() {
    try {
      await courtRequest("/court-access/end-session", { method: "POST" });
    } catch (e) {
      // Ignore
    }
    sessionStorage.removeItem("court_token");
    router.push("/court-access");
  }

  if (error) {
    return (
      <div className="p-8">
        <Alert tone="danger">{error}</Alert>
        <Button className="mt-4" onClick={endSession}>Return to Login</Button>
      </div>
    );
  }

  if (!caseDetail) {
    return <div className="p-8">Loading...</div>;
  }

  return (
    <div className="min-h-screen bg-canvas">
      <header className="sticky top-0 z-30 border-b border-subtle bg-surface px-6 py-4 shadow-sm flex justify-between items-center">
        <div className="flex items-center gap-4">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-brand text-white font-bold">
            <ScaleIcon />
          </div>
          <h1 className="text-xl font-semibold text-ink">Court View</h1>
        </div>
        <Button variant="outline" size="sm" className="text-red-600 border-red-600 hover:bg-red-50" onClick={endSession}>
          <LogOut className="mr-1.5 h-4 w-4" /> End Session
        </Button>
      </header>

      <main className="mx-auto max-w-5xl p-6 space-y-6">
        <Card>
          <CardBody>
            <div className="flex items-center gap-3 mb-2">
              <span className="font-mono text-sm text-brand">{caseDetail.case_number}</span>
              <CaseStatusBadge status={caseDetail.status} />
              <span className="text-xs bg-success text-white px-2 py-0.5 rounded-full flex items-center">
                <CheckCircle className="w-3 h-3 mr-1" /> Verified Origin
              </span>
            </div>
            <h2 className="text-2xl font-semibold tracking-tight">{caseDetail.title}</h2>
            {caseDetail.description && (
              <p className="mt-2 text-sm text-muted">{caseDetail.description}</p>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <FileText className="mr-2 h-5 w-5 text-brand" /> Documents
            </CardTitle>
          </CardHeader>
          <CardBody>
            {docs.length === 0 ? (
              <p className="text-sm text-muted">No documents found.</p>
            ) : (
              <div className="space-y-4">
                {docs.map(doc => (
                  <div key={doc.id} className="p-4 border border-subtle rounded-md flex justify-between items-center">
                    <div>
                      <h4 className="font-semibold">{doc.document_type}</h4>
                      <p className="text-xs text-muted">{doc.description || "No description"}</p>
                    </div>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" onClick={() => downloadDoc(doc.id, doc.current_version)}>
                        Download V{doc.current_version}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>

      </main>
    </div>
  );
}

function ScaleIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M2 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>
    </svg>
  );
}
