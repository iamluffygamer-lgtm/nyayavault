/** Types mirroring the FastAPI response schemas. */

export type RoleName =
  | "ADMIN"
  | "INVESTIGATOR"
  | "FORENSIC_OFFICER"
  | "LEGAL_OFFICER"
  | "AUDITOR";

export type CaseStatus =
  | "OPEN"
  | "UNDER_INVESTIGATION"
  | "SUBMITTED"
  | "CLOSED"
  | "ARCHIVED";

export type CaseAccessLevel = "READ" | "CONTRIBUTE" | "MANAGE";

export type DocumentType =
  | "FIR"
  | "CHARGE_SHEET"
  | "WITNESS_STATEMENT"
  | "FORENSIC_REPORT"
  | "SEIZURE_MEMO"
  | "COURT_ORDER"
  | "LEGAL_NOTICE"
  | "EVIDENCE_PHOTO"
  | "OTHER";

export interface Role {
  id: string;
  name: RoleName;
  description: string | null;
}

export interface Department {
  id: string;
  name: string;
  description: string | null;
}

export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  role: Role;
  department: Department | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface CaseSummary {
  id: string;
  case_number: string;
  title: string;
  status: CaseStatus;
  created_at: string;
  updated_at: string;
  created_by: string;
}

export interface CaseDetail extends CaseSummary {
  description: string | null;
  creator: User;
  document_count: number;
  access_level: CaseAccessLevel | null;
  can_upload: boolean;
}

export interface CaseStatistics {
  total_cases: number;
  active_cases: number;
  closed_cases: number;
  total_documents: number;
}

export interface CaseAssignment {
  id: string;
  user: User;
  access_level: CaseAccessLevel;
  created_at: string;
}

export interface DocumentVersion {
  id: string;
  version_number: number;
  original_filename: string;
  mime_type: string;
  file_size: number;
  sha256_hash: string;
  change_reason: string | null;
  created_at: string;
  uploader: User;
  text?: { extracted_text: string | null; extraction_method: string | null; extraction_status: string };

}

export interface DocumentSummary {
  id: string;
  case_id: string;
  title: string;
  document_type: DocumentType;
  current_version: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentListItem extends DocumentSummary {
  latest_sha256: string | null;
  latest_file_size: number | null;
  latest_filename: string | null;
  latest_uploaded_at: string | null;
}

export interface DocumentDetail extends DocumentSummary {
  description: string | null;
  creator: User;
  versions: DocumentVersion[];
}

export interface VersionVerification {
  version_number: number;
  expected_sha256: string;
  computed_sha256: string;
  verified: boolean;
  detail: string;
}

export interface IntegrityReport {
  document_id: string;
  algorithm: string;
  verified: boolean;
  results: VersionVerification[];
}

export type AuditAction =
  | "LOGIN_SUCCEEDED"
  | "LOGIN_FAILED"
  | "USER_CREATED"
  | "CASE_CREATED"
  | "CASE_VIEWED"
  | "CASE_STATUS_CHANGED"
  | "CASE_ACCESS_DENIED"
  | "CASE_MEMBER_ASSIGNED"
  | "DOCUMENT_UPLOADED"
  | "DOCUMENT_VERSION_CREATED"
  | "DOCUMENT_DOWNLOADED"
  | "DOCUMENT_INTEGRITY_VERIFIED"
  | "DOCUMENT_INTEGRITY_FAILED"
  | "UPLOAD_REJECTED";

export interface AuditEvent {
  id: string;
  action: AuditAction;
  result: "SUCCESS" | "FAILURE" | "DENIED";
  entity_type: string;
  entity_id: string | null;
  case_id: string | null;
  timestamp: string;
  actor: User | null;
  event_metadata: Record<string, unknown>;
  previous_event_hash: string;
  event_hash: string;
  event_hash_short: string;
}

export interface ChainVerificationReport {
  intact: boolean;
  events_checked: number;
  head_hash: string | null;
  broken_at_index: number | null;
  broken_event_id: string | null;
  detail: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
export * from "./evidence";
