"use client";

import { useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { FileCheck2, KeyRound, Link2, ScrollText, ShieldAlert } from "lucide-react";

import { Wordmark } from "@/components/brand";
import { Alert, Button, Input, Label, Card, CardBody, CardHeader, CardTitle } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { isAuthenticated, setSession } from "@/lib/auth";

function LoginForm() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated()) router.replace("/dashboard");
    if (typeof window !== "undefined" && window.location.search.includes("expired=1")) {
      setNotice("Your session expired. Please sign in again.");
    }
  }, [router]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const response = await api.login(username.trim(), password);
      setSession(response.access_token, response.user);
      router.replace("/dashboard");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Sign-in failed. Please verify your credentials."
      );
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg p-4 sm:p-8">
      <div className="w-full max-w-[1000px] grid md:grid-cols-[1fr_400px] bg-surface border border-line rounded-md shadow-lg overflow-hidden">
        
        {/* ------------------------------------------------ context / branding */}
        <section className="relative flex flex-col justify-between border-r border-line bg-elevated/30 p-8 md:p-12">
          <div>
            <Wordmark showSubtitle={true} />
            <div className="mt-8">
              <h1 className="text-xl font-bold tracking-tight text-ink uppercase">
                Authorized Personnel Only
              </h1>
              <p className="mt-2 text-sm leading-relaxed text-muted">
                This system is a restricted government portal for the management of legal and investigative records. Unauthorized access is strictly prohibited and logged.
              </p>
            </div>
          </div>
          
          <div className="mt-12 space-y-5 border-t border-line pt-8">
            <div className="flex gap-3">
              <ShieldAlert className="h-5 w-5 text-brand shrink-0" />
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-ink">System Notice</p>
                <p className="mt-1 text-xs leading-relaxed text-muted">
                  All activity on this portal, including successful and failed login attempts, is permanently recorded in the immutable audit log for compliance and security review.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------------- form */}
        <section className="flex flex-col justify-center p-8 md:p-10 bg-surface">
          <h2 className="text-lg font-bold tracking-tight text-ink uppercase mb-2">Portal Login</h2>
          <p className="text-xs text-muted mb-6">
            Please enter your departmental credentials to continue.
          </p>

          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            {notice && <Alert tone="info">{notice}</Alert>}
            {error && <Alert tone="danger">{error}</Alert>}

            <div>
              <Label htmlFor="username">User ID / Designation Code</Label>
              <Input
                id="username"
                name="username"
                autoComplete="username"
                autoFocus
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="Enter User ID"
                className="h-11"
              />
            </div>

            <div>
              <Label htmlFor="password">Passcode</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••••••"
                className="h-11"
              />
            </div>

            <Button
              type="submit"
              className="w-full h-12 mt-2"
              size="lg"
              loading={loading}
              disabled={!username || !password}
            >
              {loading ? "AUTHENTICATING…" : "SECURE LOGIN"}
            </Button>
          </form>

          <div className="mt-8 text-center border-t border-line pt-6">
            <p className="text-[10px] uppercase tracking-wider text-faint">
              NyayaVault Prototype System
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
