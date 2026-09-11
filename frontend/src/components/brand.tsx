import { cn } from "@/lib/utils";

/** A serious, institutional mark. */
export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={cn("h-7 w-7", className)} aria-hidden>
      <path
        d="M16 2L3 8v8.5c0 7.3 5.4 14.1 13 15.5 7.6-1.4 13-8.2 13-15.5V8L16 2z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M12 16h8m-4-4v8"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Wordmark({ className, showSubtitle = false }: { className?: string, showSubtitle?: boolean }) {
  return (
    <span className={cn("flex flex-col", className)}>
      <span className="flex items-center gap-2.5">
        <Logo className="text-brand h-6 w-6" />
        <span className="text-[16px] font-bold tracking-widest text-ink uppercase">
          NYAYAVAULT
        </span>
      </span>
      {showSubtitle && (
        <span className="mt-1 pl-8.5 text-[10px] uppercase tracking-wider text-muted font-medium ml-1">
          Secure Digital Evidence & Case Management
        </span>
      )}
    </span>
  );
}
