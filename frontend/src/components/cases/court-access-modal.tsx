import { useState } from "react";
import { Dialog } from "@/components/ui";
import { Button } from "@/components/ui";
import { Input } from "@/components/ui";
import { Alert } from "@/components/ui";
import { request } from "@/lib/api";

export function CourtAccessModal({ open, onClose, caseId }: { open: boolean; onClose: () => void; caseId: string }) {
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ reference: string; code: string } | null>(null);

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      const data = await request<any>(`/cases/${caseId}/court-access`, { method: "POST" });
      setResult(data);
    } catch (e: any) {
      setError(e.message || "Failed to generate access code.");
    } finally {
      setGenerating(false);
    }
  }

  function handleClose() {
    setResult(null);
    setError(null);
    onClose();
  }

  return (
    <Dialog open={open} onClose={handleClose} title="Generate Court Access Code">
      <div className="space-y-4">
        {result ? (
          <>
            <Alert tone="ok">Access code generated successfully.</Alert>
            <div className="space-y-2 rounded-md bg-subtle p-4 font-mono text-sm">
              <div className="flex flex-col">
                <span className="text-muted">Reference:</span>
                <span className="font-semibold text-ink">{result.reference}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-muted">Passcode:</span>
                <span className="font-semibold text-ink">{result.code}</span>
              </div>
            </div>
            <p className="text-xs text-muted">
              Copy these details and securely transmit them to the court. This passcode will only be shown once. The grant will be active for 30 days and valid for a 4-hour session upon redemption.
            </p>
            <div className="mt-4 flex justify-end">
              <Button onClick={handleClose}>Done</Button>
            </div>
          </>
        ) : (
          <>
            <p className="text-sm text-ink">
              This will generate a time-bound access code that allows a judge to view a read-only, fully-audited version of this case.
            </p>
            {error && <Alert tone="danger">{error}</Alert>}
            <div className="mt-6 flex justify-end gap-3">
              <Button variant="ghost" onClick={handleClose}>
                Cancel
              </Button>
              <Button onClick={handleGenerate} loading={generating}>
                Generate Code
              </Button>
            </div>
          </>
        )}
      </div>
    </Dialog>
  );
}
