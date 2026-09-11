"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Copy, HelpCircle, Loader2, RefreshCw, XCircle } from "lucide-react";

import { Badge } from "@/components/ui";
import { api } from "@/lib/api";
import { getCachedUser } from "@/lib/auth";
import type { BlockchainAnchor } from "@/types";

export type AnchorCheckState = "unknown" | "checking" | "anchored" | "failed" | "pending";

export function AnchorStatusBadge({
  documentId,
  versionNumber,
}: {
  documentId: string;
  versionNumber: number;
}) {
  const [state, setState] = useState<AnchorCheckState>("unknown");
  const [anchor, setAnchor] = useState<BlockchainAnchor | null>(null);
  
  const user = getCachedUser();
  const canRetry = user?.role.name !== "AUDITOR" && user?.role.name !== "LEGAL_OFFICER";

  async function checkStatus() {
    setState("checking");
    try {
      const res = await api.getAnchorStatus(documentId, versionNumber);
      setAnchor(res);
      if (res.status === "ANCHORED") {
        setState("anchored");
      } else if (res.status === "FAILED") {
        setState("failed");
      } else {
        setState("pending");
      }
    } catch (err) {
      // If it's a 404, it might mean Not Yet Anchored
      setState("unknown");
    }
  }

  useEffect(() => {
    void checkStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId, versionNumber]);

  function copyTx(e: React.MouseEvent) {
    e.stopPropagation();
    if (anchor?.tx_hash) {
      navigator.clipboard.writeText(anchor.tx_hash);
    }
  }

  if (state === "checking") {
    return (
      <Badge tone="neutral">
        <Loader2 className="h-3 w-3 animate-spin" /> Checking Chain...
      </Badge>
    );
  }

  if (state === "pending") {
    return (
      <Badge tone="neutral">
        <Loader2 className="h-3 w-3 animate-spin" /> Anchor Pending
      </Badge>
    );
  }

  if (state === "anchored") {
    return (
      <Badge tone="ok" className="group relative flex items-center gap-1 cursor-pointer" onClick={copyTx} title="Copy Transaction Hash">
        <CheckCircle2 className="h-3 w-3" />
        Anchored: {anchor?.tx_hash ? `${anchor.tx_hash.slice(0, 8)}...${anchor.tx_hash.slice(-6)}` : ""}
        <Copy className="h-3 w-3 ml-1 opacity-50 group-hover:opacity-100" />
      </Badge>
    );
  }

  if (state === "failed") {
    return (
      <div className="flex items-center gap-2">
        <Badge tone="danger">
          <XCircle className="h-3 w-3" /> Anchor Failed
        </Badge>
        {canRetry && (
          <button 
            onClick={(e) => { e.stopPropagation(); checkStatus(); }}
            className="text-xs text-muted hover:text-foreground flex items-center gap-1"
            title="Retry check"
          >
            <RefreshCw className="h-3 w-3" /> Retry
          </button>
        )}
      </div>
    );
  }

  return (
    <Badge tone="neutral">
      <HelpCircle className="h-3 w-3" /> Not yet anchored
    </Badge>
  );
}
