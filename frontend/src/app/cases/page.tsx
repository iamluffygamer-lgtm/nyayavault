"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { FolderKanban, Plus, Search } from "lucide-react";

import { CaseStatusBadge } from "@/components/cases/case-status-badge";
import { AppShell, PageHeader } from "@/components/layout/app-shell";
import {
  Alert,
  Button,
  Card,
  Dialog,
  EmptyState,
  Input,
  Label,
  Select,
  Skeleton,
  Table,
  Td,
  Textarea,
  Th,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { getCachedUser } from "@/lib/auth";
import { formatDate } from "@/lib/utils";
import type { CaseStatus, CaseSummary } from "@/types";

const STATUSES: CaseStatus[] = [
  "OPEN",
  "UNDER_INVESTIGATION",
  "SUBMITTED",
  "CLOSED",
  "ARCHIVED",
];

const CAN_OPEN_CASES = ["ADMIN", "INVESTIGATOR", "LEGAL_OFFICER"];

export default function CasesPage() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<CaseStatus | "">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const role = getCachedUser()?.role?.name;
  const canCreate = role ? CAN_OPEN_CASES.includes(role) : false;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Search and status filtering are applied by the API, which also scopes
      // the result set to the cases this user may see.
      const page = await api.listCases({ search, status });
      setCases(page.items);
      setTotal(page.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load cases.");
    } finally {
      setLoading(false);
    }
  }, [search, status]);

  useEffect(() => {
    const timer = setTimeout(() => void load(), 250); // debounce typing
    return () => clearTimeout(timer);
  }, [load]);

  async function createCase(event: React.FormEvent) {
    event.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      const created = await api.createCase({
        title: title.trim(),
        description: description.trim() || undefined,
      });
      setDialogOpen(false);
      setTitle("");
      setDescription("");
      setCases((current) => [created, ...current]);
      setTotal((current) => current + 1);
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Could not open the case.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        title="Cases"
        description={
          loading ? "Loading…" : `${total} case${total === 1 ? "" : "s"} visible to you`
        }
        action={
          canCreate ? (
            <Button size="sm" onClick={() => setDialogOpen(true)}>
              <Plus className="h-4 w-4" />
              New case
            </Button>
          ) : null
        }
      />

      {error && (
        <div className="mb-4">
          <Alert tone="danger">{error}</Alert>
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        <div className="relative min-w-[16rem] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint" />
          <Input
            className="pl-9"
            placeholder="Search by case number or title…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            aria-label="Search cases"
          />
        </div>
        <Select
          className="w-52"
          value={status}
          onChange={(event) => setStatus(event.target.value as CaseStatus | "")}
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          {STATUSES.map((value) => (
            <option key={value} value={value}>
              {value.replace(/_/g, " ")}
            </option>
          ))}
        </Select>
      </div>

      <Card>
        {loading ? (
          <div className="space-y-2 p-5">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
          </div>
        ) : cases.length === 0 ? (
          <EmptyState
            icon={<FolderKanban className="h-6 w-6" />}
            title={search || status ? "No cases match this filter" : "No cases yet"}
            description={
              search || status
                ? "Try a different search term or clear the status filter."
                : canCreate
                  ? "Open the first case to start recording documents and evidence."
                  : "You will see cases here once you are assigned to one."
            }
            action={
              canCreate && !search && !status ? (
                <Button size="sm" onClick={() => setDialogOpen(true)}>
                  <Plus className="h-4 w-4" />
                  New case
                </Button>
              ) : null
            }
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Case number</Th>
                <Th>Title</Th>
                <Th>Status</Th>
                <Th>Opened</Th>
                <Th>Last updated</Th>
              </tr>
            </thead>
            <tbody>
              {cases.map((item) => (
                <tr key={item.id} className="group hover:bg-elevated/60">
                  <Td>
                    <Link
                      href={`/cases/${item.id}`}
                      className="font-mono text-xs text-brand hover:underline"
                    >
                      {item.case_number}
                    </Link>
                  </Td>
                  <Td className="max-w-[24rem]">
                    <Link href={`/cases/${item.id}`} className="hover:underline">
                      {item.title}
                    </Link>
                  </Td>
                  <Td>
                    <CaseStatusBadge status={item.status} />
                  </Td>
                  <Td className="whitespace-nowrap text-xs text-muted">
                    {formatDate(item.created_at)}
                  </Td>
                  <Td className="whitespace-nowrap text-xs text-muted">
                    {formatDate(item.updated_at)}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title="Open a new case"
        description="The case number is allocated by the server and cannot be chosen."
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              form="new-case-form"
              type="submit"
              loading={creating}
              disabled={title.trim().length < 3}
            >
              Open case
            </Button>
          </>
        }
      >
        <form id="new-case-form" onSubmit={createCase} className="space-y-4">
          {createError && <Alert tone="danger">{createError}</Alert>}
          <div>
            <Label htmlFor="case-title">Case title</Label>
            <Input
              id="case-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="e.g. Unauthorised access to municipal records server"
              maxLength={255}
              autoFocus
              required
            />
          </div>
          <div>
            <Label htmlFor="case-description">Description (optional)</Label>
            <Textarea
              id="case-description"
              rows={4}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Background, complainant details, jurisdiction…"
            />
          </div>
        </form>
      </Dialog>
    </AppShell>
  );
}
