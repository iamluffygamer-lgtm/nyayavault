"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Plus, ShieldCheck, ShieldAlert } from "lucide-react";

import {
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  EmptyState,
  Table,
  Td,
  Th,
  Badge,
} from "@/components/ui";
import { api } from "@/lib/api";
import { EvidenceRead } from "@/types/evidence";
import { titleCase } from "@/lib/utils";

export function EvidenceList({ caseId }: { caseId: string }) {
  const [evidence, setEvidence] = useState<EvidenceRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listEvidence(caseId)
      .then(setEvidence)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [caseId]);

  if (loading) return <div className="p-4 text-sm text-muted">Loading evidence...</div>;
  if (error) return <div className="p-4 text-sm text-danger">{error}</div>;

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle>Case Evidence</CardTitle>
        <Link href={`/cases/${caseId}/evidence/new`}>
          <Button variant="primary" size="sm">
            <Plus className="mr-2 h-4 w-4" />
            Register Evidence
          </Button>
        </Link>
      </CardHeader>
      <CardBody>
        {evidence.length === 0 ? (
          <EmptyState
            icon={<ShieldAlert className="h-8 w-8 text-muted" />}
            title="No evidence registered"
            description="Register evidence to track chain of custody."
            action={
              <Link href={`/cases/${caseId}/evidence/new`}>
                <Button variant="primary">Register Evidence</Button>
              </Link>
            }
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Number</Th>
                <Th>Title</Th>
                <Th>Type</Th>
                <Th>Status</Th>
                <Th>Custodian</Th>
                <Th>Integrity</Th>
              </tr>
            </thead>
            <tbody>
              {evidence.map((ev) => (
                <tr key={ev.id}>
                  <Td>
                    <Link href={`/evidence/${ev.id}`} className="font-medium text-brand hover:underline">
                      {ev.evidence_number}
                    </Link>
                  </Td>
                  <Td>{ev.title}</Td>
                  <Td>{titleCase(ev.evidence_type)}</Td>
                  <Td>
                    <Badge tone="neutral">{ev.status}</Badge>
                  </Td>
                  <Td>{ev.custodian?.full_name || ev.custodian?.username || "Unknown"}</Td>
                  <Td>
                    {ev.sha256_hash ? (
                      <span className="inline-flex items-center gap-1 text-ok">
                        <ShieldCheck className="h-3 w-3" /> Hash linked
                      </span>
                    ) : (
                      <span className="text-muted text-xs">No file</span>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </CardBody>
    </Card>
  );
}
