"use client";

import { FileText, FolderOpen, ShieldCheck, Activity, Link, ShieldAlert, Package, MoveRight } from "lucide-react";
import { formatDate } from "@/lib/utils";

export interface TimelineEvent {
  id: string;
  timestamp: string;
  actor_name: string;
  action: string;
  summary: string;
  icon_hint: string;
}

export function CaseTimeline({ events, loading = false }: { events: TimelineEvent[], loading?: boolean }) {
  if (loading) {
    return <div className="p-4 text-center text-sm text-muted">Loading timeline...</div>;
  }

  if (events.length === 0) {
    return (
      <div className="p-4 text-center text-sm text-muted">
        No events recorded yet.
      </div>
    );
  }

  return (
    <div className="space-y-6 px-5 py-4">
      {events.map((e, i) => {
        const isLast = i === events.length - 1;
        
        let Icon = Activity;
        let colorClass = "text-brand border-brand/20 bg-brand/10";
        
        if (e.icon_hint === "case") Icon = FolderOpen;
        else if (e.icon_hint === "document") Icon = FileText;
        else if (e.icon_hint === "evidence") Icon = Package;
        else if (e.icon_hint === "transfer") Icon = MoveRight;
        else if (e.icon_hint === "blockchain") {
          Icon = Link;
          colorClass = "text-ok border-ok/20 bg-ok/10";
        }
        else if (e.icon_hint === "alert") {
          Icon = ShieldAlert;
          colorClass = "text-danger border-danger/20 bg-danger/10";
        }

        return (
          <div key={e.id} className="relative flex gap-4">
            {!isLast && (
              <div className="absolute left-3 top-8 -ml-px h-full w-0.5 bg-line/60" />
            )}
            <div className={`relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border ${colorClass}`}>
              <Icon className="h-3 w-3" />
            </div>
            <div className="pb-2">
              <div className="text-sm font-medium text-ink">
                {e.summary}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
                <span>{formatDate(e.timestamp)}</span>
                <span aria-hidden>&middot;</span>
                <span className="font-mono text-[10px] uppercase opacity-70">{e.action}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
