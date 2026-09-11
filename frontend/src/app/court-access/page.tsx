"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Scale } from "lucide-react";
import { Button } from "@/components/ui";
import { Input } from "@/components/ui";
import { Alert, Label } from "@/components/ui";
import { courtRequest } from "@/lib/court-api";

export default function CourtAccessPage() {
  const router = useRouter();
  const [reference, setReference] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRedeem(e: any) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await courtRequest<any>("/court-access/redeem", {
        method: "POST",
        body: { reference, code },
        unauthenticated: true,
      });
      sessionStorage.setItem("court_token", data.token);
      router.push("/court-access/case");
    } catch (err: any) {
      setError(err.message || "Invalid access code.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        <div className="flex flex-col items-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand">
            <Scale className="h-6 w-6 text-white" />
          </div>
          <h2 className="mt-6 text-center text-3xl font-bold tracking-tight text-ink">
            Court Portal
          </h2>
          <p className="mt-2 text-center text-sm text-muted">
            Redeem access code to view case evidence
          </p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleRedeem}>
          {error && <Alert tone="danger">{error}</Alert>}
          <div className="space-y-4 rounded-md">
            <div>

              <Label>Reference</Label>
              <Input
                required
                value={reference}
                onChange={(e: any) => setReference(e.target.value)}
              />

            </div>
            <div>

              <Label>Passcode</Label>
              <Input
                type="password"
                required
                value={code}
                onChange={(e: any) => setCode(e.target.value)}
              />

            </div>
          </div>

          <div>
            <Button type="submit" className="w-full" loading={loading}>
              Access Case Files
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
