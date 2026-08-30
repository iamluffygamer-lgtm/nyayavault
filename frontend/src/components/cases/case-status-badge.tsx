import { Badge } from "@/components/ui";
import { titleCase } from "@/lib/utils";
import type { CaseStatus } from "@/types";

const TONES: Record<CaseStatus, "info" | "warn" | "brand" | "ok" | "neutral"> = {
  OPEN: "info",
  UNDER_INVESTIGATION: "warn",
  SUBMITTED: "brand",
  CLOSED: "ok",
  ARCHIVED: "neutral",
};

export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  return <Badge tone={TONES[status]}>{titleCase(status)}</Badge>;
}
