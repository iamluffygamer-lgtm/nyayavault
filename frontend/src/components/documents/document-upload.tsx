"use client";

import { useRef, useState } from "react";
import { FileUp, Paperclip, X } from "lucide-react";

import { Alert, Button, Input, Label, Select, Textarea } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { formatBytes, titleCase } from "@/lib/utils";
import type { DocumentType } from "@/types";

const DOCUMENT_TYPES: DocumentType[] = [
  "FIR",
  "CHARGE_SHEET",
  "WITNESS_STATEMENT",
  "FORENSIC_REPORT",
  "SEIZURE_MEMO",
  "COURT_ORDER",
  "LEGAL_NOTICE",
  "EVIDENCE_PHOTO",
  "OTHER",
];

// Mirrors the server-side allow-list. This is a convenience for the file
// picker only — the backend re-validates the extension, sniffs the actual
// content and enforces the size limit regardless of what is sent.
const ACCEPT = ".pdf,.png,.jpg,.jpeg,.tif,.tiff,.txt,.docx,.doc";
const MAX_BYTES = 50 * 1024 * 1024;

export function DocumentUpload({
  caseId,
  onUploaded,
}: {
  caseId: string;
  onUploaded: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [documentType, setDocumentType] = useState<DocumentType>("OTHER");
  const [description, setDescription] = useState("");
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  function chooseFile(selected: File | null) {
    setError(null);
    setSuccess(null);
    if (!selected) return;
    if (selected.size > MAX_BYTES) {
      setError(`That file is ${formatBytes(selected.size)}. The limit is 50 MB.`);
      return;
    }
    setFile(selected);
    if (!title) {
      setTitle(selected.name.replace(/\.[^.]+$/, "").slice(0, 120));
    }
  }

  function reset() {
    setFile(null);
    setTitle("");
    setDescription("");
    setDocumentType("OTHER");
    if (inputRef.current) inputRef.current.value = "";
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;

    setUploading(true);
    setError(null);
    setSuccess(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("title", title.trim() || file.name);
      form.append("document_type", documentType);
      if (description.trim()) form.append("description", description.trim());

      const created = await api.uploadDocument(caseId, form);
      const hash = created.versions[0]?.sha256_hash ?? "";
      setSuccess(`Stored as version 1. SHA-256 ${hash.slice(0, 16)}…`);
      reset();
      onUploaded();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The upload failed.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 px-5 py-4">
      {error && <Alert tone="danger">{error}</Alert>}
      {success && <Alert tone="ok">{success}</Alert>}

      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          chooseFile(event.dataTransfer.files?.[0] ?? null);
        }}
        className={`rounded-lg border border-dashed px-4 py-6 text-center transition-colors ${
          dragging ? "border-brand bg-brand/5" : "border-line bg-elevated/50"
        }`}
      >
        {file ? (
          <div className="flex items-center justify-center gap-2 text-xs">
            <Paperclip className="h-3.5 w-3.5 text-brand" />
            <span className="max-w-[16rem] truncate font-medium">{file.name}</span>
            <span className="text-faint">{formatBytes(file.size)}</span>
            <button
              type="button"
              onClick={reset}
              className="text-faint hover:text-danger"
              aria-label="Remove selected file"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : (
          <>
            <FileUp className="mx-auto h-5 w-5 text-faint" />
            <p className="mt-2 text-xs text-muted">
              Drop a file here, or{" "}
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="text-brand underline underline-offset-2"
              >
                browse
              </button>
            </p>
            <p className="mt-1 text-[11px] text-faint">
              PDF, DOCX, DOC, PNG, JPG, TIFF or TXT · up to 50 MB
            </p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <Label htmlFor="doc-title">Document title</Label>
          <Input
            id="doc-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="e.g. Final charge sheet"
            maxLength={255}
            required
          />
        </div>
        <div>
          <Label htmlFor="doc-type">Document type</Label>
          <Select
            id="doc-type"
            value={documentType}
            onChange={(event) => setDocumentType(event.target.value as DocumentType)}
          >
            {DOCUMENT_TYPES.map((value) => (
              <option key={value} value={value}>
                {titleCase(value)}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <div>
        <Label htmlFor="doc-description">Notes (optional)</Label>
        <Textarea
          id="doc-description"
          rows={2}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Context a reviewer would need…"
        />
      </div>

      <div className="flex items-center justify-between gap-3">
        <p className="text-[11px] leading-relaxed text-faint">
          The file is hashed with SHA-256 on receipt and stored as version 1.
          Existing documents are never overwritten.
        </p>
        <Button type="submit" size="sm" loading={uploading} disabled={!file || !title.trim()}>
          Upload
        </Button>
      </div>
    </form>
  );
}
