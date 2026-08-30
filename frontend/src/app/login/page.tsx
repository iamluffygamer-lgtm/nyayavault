"use client";

import { useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { FileCheck2, KeyRound, Link2, ScrollText } from "lucide-react";

import { Wordmark } from "@/components/brand";
import { Alert, Button, Input, Label } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { isAuthenticated, setSession } from "@/lib/auth";

const CAPABILITIES = [
  {
    icon: <FileCheck2 className="h-4 w-4" />,
    title: "SHA-256 at ingest",
    body: "Every uploaded version is hashed from the received bytes and can be re-verified on demand.",
  },
  {
    icon: <ScrollText className="h-4 w-4" />,
    title: "Immutable versions",
    body: "Revisions append. A previous version's bytes and hash are never overwritten.",
  },
  {
    icon: <Link2 className="h-4 w-4" />,
    title: "Hash-linked audit trail",
    body: "Each event carries the hash of the one before it, so edits to history are detectable.",
  },
  {
    icon: <KeyRound className="h-4 w-4" />,
    title: "Role and case-level access",
    body: "Authorisation is resolved server-side from the database on every single request.",
  },
];

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
        err instanceof ApiError ? err.message : "Sign-in failed. Please try again."
      );
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      {/* ------------------------------------------------ context / branding */}
      <section className="relative hidden flex-col justify-between border-r border-line bg-surface/40 p-10 lg:flex">
        <Wordmark />

        <div className="max-w-md">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-brand">
            Problem statement 26190
          </p>
          <h1 className="mt-3 text-3xl font-semibold leading-tight tracking-tight">
            Secure digital document management for legal and investigation records.
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-muted">
            A case-centric vault where every document carries a verifiable fingerprint and
            every action leaves a record that cannot be quietly rewritten.
          </p>

          <ul className="mt-8 space-y-4">
            {CAPABILITIES.map((item) => (
              <li key={item.title} className="flex gap-3">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-line bg-elevated text-brand">
                  {item.icon}
                </span>
                <div>
                  <p className="text-xs font-medium text-ink">{item.title}</p>
                  <p className="mt-0.5 text-xs leading-relaxed text-muted">{item.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="text-[11px] text-faint">
          Milestone&nbsp;0 prototype · not production-hardened · Smart India Hackathon
        </p>
      </section>

      {/* ------------------------------------------------------------- form */}
      <section className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-sm">
          <div className="lg:hidden">
            <Wordmark />
          </div>

          <h2 className="mt-8 text-xl font-semibold tracking-tight lg:mt-0">Sign in</h2>
          <p className="mt-1 text-xs text-muted">
            Accounts are provisioned by an administrator. There is no public sign-up.
          </p>

          <form onSubmit={onSubmit} className="mt-6 space-y-4" noValidate>
            {notice && <Alert tone="info">{notice}</Alert>}
            {error && <Alert tone="danger">{error}</Alert>}

            <div>
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                name="username"
                autoComplete="username"
                autoFocus
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="e.g. r.sharma"
              />
            </div>

            <div>
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••••••"
              />
            </div>

            <Button
              type="submit"
              className="w-full"
              size="lg"
              loading={loading}
              disabled={!username || !password}
            >
              {loading ? "Signing in…" : "Sign in"}
            </Button>
          </form>

          <p className="mt-6 text-[11px] leading-relaxed text-faint">
            Every sign-in attempt, successful or not, is written to the audit trail.
          </p>
        </div>
      </section>
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
