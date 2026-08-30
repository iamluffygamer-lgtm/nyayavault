"use client";

import { EvidenceTransferRead } from "@/types/evidence";
import { formatBytes, formatDate, relativeTime } from "@/lib/utils";

export function CustodyTimeline({ transfers }: { transfers: EvidenceTransferRead[] }) {
  if (transfers.length === 0) {
    return (
      <div className="p-4 text-center text-sm text-muted">
        No transfers recorded. Evidence is with its original custodian.
      </div>
    );
  }

  return (
    <div className="space-y-6 px-5 py-4">
      {transfers.map((t, i) => {
        const isLast = i === transfers.length - 1;
        return (
          <div key={t.id} className="relative flex gap-4">
            {!isLast && (
              <div className="absolute left-3 top-8 -ml-px h-full w-0.5 bg-line/60" />
            )}
            <div className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-brand/20 bg-brand/10 text-brand">
              <span className="text-[10px] font-bold">{i + 1}</span>
            </div>
            <div className="pb-2">
              <div className="text-sm font-medium text-ink">
                Transfer from <span className="text-brand">{t.from_user.full_name || t.from_user.username}</span> to <span className="text-brand">{t.to_user.full_name || t.to_user.username}</span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
                <span>Initiated: {formatDate(t.transferred_at)}</span>
                {t.received_at && (
                  <>
                    <span aria-hidden>&middot;</span>
                    <span>Received: {formatDate(t.received_at)}</span>
                  </>
                )}
                <span aria-hidden>&middot;</span>
                <span className="font-medium">Status: {t.status}</span>
              </div>
              {t.reason && (
                <div className="mt-2 text-xs text-muted">Reason: {t.reason}</div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
