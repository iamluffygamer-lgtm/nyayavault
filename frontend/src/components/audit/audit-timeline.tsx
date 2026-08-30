"use client";

import {
  AlertTriangle,
  Download,
  FilePlus2,
  FolderPlus,
  LogIn,
  ShieldCheck,
  ShieldX,
  UserPlus,
  Users,
  XCircle,
} from "lucide-react";

import { EmptyState } from "@/components/ui";
import { relativeTime, shortHash, titleCase } from "@/lib/utils";
import type { AuditAction, AuditEvent } from "@/types";

const ICONS: Partial<Record<AuditAction, React.ReactNode>> = {
  LOGIN_SUCCEEDED: <LogIn className="h-3.5 w-3.5" />,
  LOGIN_FAILED: <XCircle className="h-3.5 w-3.5" />,
  USER_CREATED: <UserPlus className="h-3.5 w-3.5" />,
  CASE_CREATED: <FolderPlus className="h-3.5 w-3.5" />,
  CASE_MEMBER_ASSIGNED: <Users className="h-3.5 w-3.5" />,
  DOCUMENT_UPLOADED: <FilePlus2 className="h-3.5 w-3.5" />,
  DOCUMENT_VERSION_CREATED: <FilePlus2 className="h-3.5 w-3.5" />,
  DOCUMENT_DOWNLOADED: <Download className="h-3.5 w-3.5" />,
  DOCUMENT_INTEGRITY_VERIFIED: <ShieldCheck className="h-3.5 w-3.5" />,
  DOCUMENT_INTEGRITY_FAILED: <ShieldX className="h-3.5 w-3.5" />,
  UPLOAD_REJECTED: <AlertTriangle className="h-3.5 w-3.5" />,
};

function toneFor(event: AuditEvent): string {
  if (event.result === "FAILURE" || event.result === "DENIED") return "text-danger";
  if (event.action === "DOCUMENT_INTEGRITY_VERIFIED") return "text-ok";
  return "text-brand";
}

function describe(event: AuditEvent): string {
  const meta = event.event_metadata ?? {};
  const actor = event.actor?.full_name || event.actor?.username || "Unknown actor";

  switch (event.action) {
    case "CASE_CREATED":
      return `${actor} opened case ${meta.case_number ?? ""}`.trim();
    case "CASE_VIEWED":
      return `${actor} viewed the case`;
    case "CASE_STATUS_CHANGED":
      return `${actor} moved the case from ${titleCase(String(meta.from ?? ""))} to ${titleCase(
        String(meta.to ?? "")
      )}`;
    case "CASE_MEMBER_ASSIGNED":
      return `${actor} granted ${meta.member ?? "a user"} ${String(
        meta.access_level ?? ""
      ).toLowerCase()} access`;
    case "DOCUMENT_UPLOADED":
      return `${actor} uploaded "${meta.document_title ?? "a document"}"`;
    case "DOCUMENT_VERSION_CREATED":
      return `${actor} added version ${meta.version_number} of "${meta.document_title ?? "a document"}"`;
    case "DOCUMENT_DOWNLOADED":
      return `${actor} downloaded version ${meta.version_number}`;
    case "DOCUMENT_INTEGRITY_VERIFIED":
      return `${actor} verified document integrity — hashes match`;
    case "DOCUMENT_INTEGRITY_FAILED":
      return `${actor} ran an integrity check and it FAILED`;
    case "UPLOAD_REJECTED":
      return `${actor} attempted an upload that was rejected (${meta.reason ?? "policy"})`;
    case "LOGIN_SUCCEEDED":
      return `${actor} signed in`;
    case "LOGIN_FAILED":
      return `Failed sign-in attempt (${meta.reason ?? "invalid credentials"})`;
    case "USER_CREATED":
      return `${actor} created the account "${meta.username ?? ""}"`;
    default:
      return `${actor} — ${titleCase(event.action)}`;
  }
}

export function AuditTimeline({ events }: { events: AuditEvent[] }) {
  if (events.length === 0) {
    return (
      <EmptyState
        title="No recorded activity yet"
        description="Every action taken on this case will be appended to the hash-linked audit trail and appear here."
      />
    );
  }

  return (
    <ol className="relative space-y-0">
      {events.map((event, index) => (
        <li key={event.id} className="relative flex gap-3 px-5 py-3">
          {index !== events.length - 1 && (
            <span className="absolute left-[30px] top-9 h-[calc(100%-1.25rem)] w-px bg-line" aria-hidden />
          )}
          <span
            className={`relative z-10 mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-line bg-elevated ${toneFor(
              event
            )}`}
          >
            {ICONS[event.action] ?? <ShieldCheck className="h-3.5 w-3.5" />}
          </span>

          <div className="min-w-0 flex-1">
            <p className="text-xs text-ink">{describe(event)}</p>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-faint">
              <span>{relativeTime(event.timestamp)}</span>
              {/* The chain hash is shown so a reviewer can tie a screen to a record. */}
              <span className="hash" title={`Event hash: ${event.event_hash}`}>
                {shortHash(event.event_hash, 10)}
              </span>
              {event.result !== "SUCCESS" && (
                <span className="font-medium text-danger">{event.result}</span>
              )}
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
