import { cn } from "@/lib/utils";

/** The NyayaVault mark: a vault door drawn as the scales of justice. */
export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={cn("h-7 w-7", className)} aria-hidden>
      <rect
        x="2.5"
        y="3.5"
        width="27"
        height="25"
        rx="4"
        stroke="currentColor"
        strokeWidth="1.75"
        opacity="0.55"
      />
      <circle cx="16" cy="16" r="7.5" stroke="currentColor" strokeWidth="1.75" />
      <path d="M16 8.5v15" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
      <path d="M8.5 16h15" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
      <circle cx="16" cy="16" r="2.25" fill="currentColor" />
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2", className)}>
      <Logo className="text-brand" />
      <span className="text-[15px] font-semibold tracking-tight">
        Nyaya<span className="text-brand">Vault</span>
      </span>
    </span>
  );
}
