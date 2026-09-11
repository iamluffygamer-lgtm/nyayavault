"use client";

import { clearSession, getToken } from "@/lib/auth";
import type {
  AuditEvent,
  CaseAssignment,
  CaseDetail,
  CaseStatistics,
  CaseStatus,
  CaseSummary,
  ChainVerificationReport,
  Department,
  DocumentDetail,
  DocumentListItem,
  DocumentVersion,
  IntegrityReport,
  LoginResponse,
  Page,
  Role,
  User,
} from "@/types";

export const BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/$/,
  ""
);
export const PREFIX = "/api/v1";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly code?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  formData?: FormData;
  signal?: AbortSignal;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, formData, signal } = options;

  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  // Content-Type is left unset for FormData so the browser can add the
  // multipart boundary itself.
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${PREFIX}${path}`, {
      method,
      headers,
      body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
      signal,
      cache: "no-store",
    });
  } catch (error) {
    if ((error as Error).name === "AbortError") throw error;
    throw new ApiError(0, "Cannot reach the NyayaVault API. Is the backend running?");
  }

  if (response.status === 401) {
    // The token is gone or expired: drop it and send the user back to sign in.
    clearSession();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login?expired=1";
    }
    throw new ApiError(401, "Your session has expired. Please sign in again.");
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    let code: string | undefined;
    try {
      const payload = await response.json();
      message = payload?.error?.message ?? message;
      code = payload?.error?.code;
      const details = payload?.error?.details;
      if (Array.isArray(details) && details.length > 0) {
        message = `${message} ${details.map((d: { field: string; issue: string }) => `${d.field}: ${d.issue}`).join("; ")}`;
      }
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, message, code);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  // ----------------------------------------------------------------- auth
  login: (username: string, password: string) =>
    request<LoginResponse>("/auth/login", {
      method: "POST",
      body: { username, password },
    }),

  me: () => request<User>("/auth/me"),

  // ---------------------------------------------------------------- cases
  listCases: (params: { search?: string; status?: CaseStatus | ""; limit?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.status) query.set("status", params.status);
    query.set("limit", String(params.limit ?? 100));
    return request<Page<CaseSummary>>(`/cases?${query.toString()}`);
  },

  getCase: (caseId: string) => request<CaseDetail>(`/cases/${caseId}`),

  createCase: (payload: { title: string; description?: string; status?: CaseStatus }) =>
    request<CaseDetail>("/cases", { method: "POST", body: payload }),

  updateCaseStatus: (caseId: string, status: CaseStatus) =>
    request<CaseSummary>(`/cases/${caseId}/status`, { method: "PATCH", body: { status } }),

  statistics: () => request<CaseStatistics>("/cases/statistics"),

  listCaseMembers: (caseId: string) =>
    request<CaseAssignment[]>(`/cases/${caseId}/members`),

  getCaseTimeline: (caseId: string, limit = 50, offset = 0) =>
    request<Page<import("@/components/cases/case-timeline").TimelineEvent>>(`/cases/${caseId}/timeline?limit=${limit}&offset=${offset}`),

  caseAudit: (caseId: string, limit = 25) =>
    request<Page<AuditEvent>>(`/cases/${caseId}/audit?limit=${limit}`),

  // ------------------------------------------------------------ documents
  listDocuments: (caseId: string) =>
    request<DocumentListItem[]>(`/cases/${caseId}/documents`),

  getDocument: (documentId: string) => request<DocumentDetail>(`/documents/${documentId}`),

  listVersions: (documentId: string) =>
    request<DocumentVersion[]>(`/documents/${documentId}/versions`),

  verifyDocument: (documentId: string) =>
    request<IntegrityReport>(`/documents/${documentId}/verify`),

  getAnchorStatus: (documentId: string, versionNumber: number) =>
    request<import("@/types").BlockchainAnchor>(`/documents/${documentId}/versions/${versionNumber}/anchor`),

  verifyChain: (documentId: string, versionNumber: number) =>
    request<import("@/types").VerifyChainResult>(`/documents/${documentId}/versions/${versionNumber}/verify-chain`),

  demoTamper: (documentId: string, versionNumber: number) =>
    request<{ status: string; new_key: string }>(`/documents/${documentId}/versions/${versionNumber}/demo-tamper`, {
      method: "POST"
    }),

  uploadDocument: (caseId: string, form: FormData) =>
    request<DocumentDetail>(`/cases/${caseId}/documents`, { method: "POST", formData: form }),

  uploadVersion: (documentId: string, form: FormData) =>
    request<DocumentVersion>(`/documents/${documentId}/versions`, {
      method: "POST",
      formData: form,
    }),

  /**
   * Downloads go through the API, never straight to object storage, so the
   * request has to carry the bearer token. That rules out a plain <a href>;
   * the response is fetched as a blob and handed to the browser instead.
   */
  downloadDocument: async (documentId: string, filename: string, version?: number) => {
    const token = getToken();
    const query = version ? `?version=${version}` : "";
    const response = await fetch(
      `${BASE_URL}${PREFIX}/documents/${documentId}/download${query}`,
      { headers: token ? { Authorization: `Bearer ${token}` } : {} }
    );
    if (!response.ok) {
      throw new ApiError(response.status, "The download was refused.");
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.URL.revokeObjectURL(url);
  },

  // ---------------------------------------------------------------- audit
  auditEvents: (limit = 25) => request<Page<AuditEvent>>(`/audit/events?limit=${limit}`),

  verifyAuditChain: () => request<ChainVerificationReport>("/audit/verify"),

  // ------------------------------------------------------- reference data
  listRoles: () => request<Role[]>("/roles"),
  listDepartments: () => request<Department[]>("/departments"),
  // Admin Methods
  createUser: (data: any) =>
    request<User>("/users", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateUser: (id: string, data: any) =>
    request<User>(`/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  createDepartment: (data: any) =>
    request<Department>("/departments", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateDepartment: (id: string, data: any) =>
    request<Department>(`/departments/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  listUsers: (limit = 100) => request<Page<User>>(`/users?limit=${limit}`),

  // ------------------------------------------------------------- evidence
  getEvidenceTimeline: (evidenceId: string, limit = 50, offset = 0) =>
    request<Page<import("@/components/cases/case-timeline").TimelineEvent>>(`/evidence/${evidenceId}/timeline?limit=${limit}&offset=${offset}`),

  listEvidence: (caseId: string) => request<any[]>(`/cases/${caseId}/evidence`),
  createEvidence: (caseId: string, data: any) =>
    request<any>(`/cases/${caseId}/evidence`, { method: "POST", body: data }),
  getEvidence: (evidenceId: string) => request<any>(`/evidence/${evidenceId}`),
  updateEvidenceStatus: (evidenceId: string, action: string) =>
    request<any>(`/evidence/${evidenceId}/${action}`, { method: "POST" }),
  listTransfers: (evidenceId: string) => request<any[]>(`/evidence/${evidenceId}/transfers`),
  createTransfer: (evidenceId: string, data: any) =>
    request<any>(`/evidence/${evidenceId}/transfers`, { method: "POST", body: data }),
  acceptTransfer: (transferId: string) =>
    request<any>(`/transfers/${transferId}/accept`, { method: "POST" }),
  rejectTransfer: (transferId: string) =>
    request<any>(`/transfers/${transferId}/reject`, { method: "POST" }),
  verifyEvidence: (evidenceId: string) => request<any>(`/evidence/${evidenceId}/verify`),

  searchDocuments: (params: {
    q?: string;
    case_id?: string;
    document_type?: string;
    page?: number;
    page_size?: number;
  }) => {
    const searchParams = new URLSearchParams();
    if (params.q) searchParams.append("q", params.q);
    if (params.case_id) searchParams.append("case_id", params.case_id);
    if (params.document_type) searchParams.append("document_type", params.document_type);
    if (params.page) searchParams.append("page", params.page.toString());
    if (params.page_size) searchParams.append("page_size", params.page_size.toString());
    
    return request<any>(`/search?${searchParams.toString()}`);
  },
  
  triggerOCR: (documentId: string, version: number) => {
    return request<any>(`/documents/${documentId}/versions/${version}/ocr`, {
      method: "POST"
    });
  }
};
