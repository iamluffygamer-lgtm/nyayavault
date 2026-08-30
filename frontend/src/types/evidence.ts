export type EvidenceStatus =
  | "COLLECTED"
  | "REGISTERED"
  | "SEALED"
  | "IN_CUSTODY"
  | "TRANSFER_PENDING"
  | "UNDER_ANALYSIS"
  | "ANALYZED"
  | "COURT_SUBMITTED"
  | "ARCHIVED";

export type TransferStatus = "PENDING" | "COMPLETED" | "REJECTED";

export interface EvidenceRead {
  id: string;
  case_id: string;
  evidence_number: string;
  title: string;
  description: string | null;
  evidence_type: string;
  status: EvidenceStatus;
  collected_at: string | null;
  collected_location: string | null;
  collected_by: string | null;
  current_custodian: string | null;
  source_document_id: string | null;
  sha256_hash: string | null;
  created_at: string;
  updated_at: string;
  collector: any | null; // using any for UserRead shorthand here, will fix if needed
  custodian: any | null;
  source_document: any | null;
}

export interface EvidenceCreate {
  title: string;
  description?: string;
  evidence_type: string;
  collected_at?: string;
  collected_location?: string;
  collected_by?: string;
  source_document_id?: string;
}

export interface EvidenceTransferCreate {
  to_user_id: string;
  reason?: string;
  location?: string;
}

export interface EvidenceTransferRead {
  id: string;
  evidence_id: string;
  from_user_id: string;
  to_user_id: string;
  transferred_at: string;
  received_at: string | null;
  reason: string | null;
  location: string | null;
  status: TransferStatus;
  created_at: string;
  from_user: any;
  to_user: any;
}

export interface IntegrityVerificationResult {
  evidence_id: string;
  source_document_id: string;
  expected_hash: string;
  actual_hash: string;
  is_intact: boolean;
  verified_at: string;
}
