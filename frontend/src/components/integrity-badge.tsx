"use client";

import { CheckCircle2, HelpCircle, Loader2, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui";

export type IntegrityState = "unknown" | "checking" | "verified" | "failed";

/**
 * Deliberately shows "Not verified" until a check has actually run.
 * Displaying a green tick for an unverified document would be exactly the kind
 * of decorative security the brief rules out.
 */
export function IntegrityBadge({ state }: { state: IntegrityState }) {
  if (state === "checking") {
    return (
      <Badge tone="neutral">
        <Loader2 className="h-3 w-3 animate-spin" /> Checking
      </Badge>
    );
  }
  if (state === "verified") {
    return (
      <Badge tone="ok">
        <CheckCircle2 className="h-3 w-3" /> Integrity verified
      </Badge>
    );
  }
  if (state === "failed") {
    return (
      <Badge tone="danger">
        <ShieldAlert className="h-3 w-3" /> Integrity failed
      </Badge>
    );
  }
  return (
    <Badge tone="neutral">
      <HelpCircle className="h-3 w-3" /> Not verified
    </Badge>
  );
}
