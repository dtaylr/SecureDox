export type DocumentStatus =
  | "RECEIVED"
  | "QUEUED"
  | "EXTRACTING"
  | "VALIDATING"
  | "REVIEW_REQUIRED"
  | "VALIDATED"
  | "REJECTED"
  | "FAILED"
  | "QUARANTINED";

export type Role = "admin" | "reviewer" | "uploader";

export type LoginRequest = {
  username: Role;
  password?: string;
  tenantId?: string;
};

export type DocumentSummary = {
  id: string;
  document_type: string;
  status: DocumentStatus;
  original_filename: string;
  size_bytes: number;
  created_at: string;
  processed_at: string | null;
};

export type ErrorResponse = {
  error: {
    code: string;
    message: string;
    correlation_id: string;
    details: Array<{ field: string | null; rule_id?: string | null; message: string }>;
  };
};

export type ExtractedField = {
  field_name: string;
  value: string | null;
  display_value: string | null;
  confidence: number;
  source: string;
  is_pii: boolean;
};

export type DocumentDetail = DocumentSummary & {
  mime_type: string;
  correlation_id: string;
  page_count: number | null;
  ocr_provider: string | null;
  rejection_reason: string | null;
  needs_manual_review: boolean;
  extracted_fields: ExtractedField[];
  validation_results: Array<{
    rule_id: string;
    field_name: string;
    status: "PASS" | "WARN" | "FAIL";
    severity: string;
    message: string;
    is_blocking: boolean;
  }>;
};

export type UploadResult = {
  id: string;
  status: DocumentStatus;
  document_type: string;
  correlation_id: string;
};

export type AuditEvent = {
  id: string;
  document_id: string | null;
  action: string;
  actor: string;
  correlation_id: string;
  detail: Record<string, unknown>;
  created_at: string;
};

export type AdminStatus = {
  tenant_id: string;
  queue_depth: number;
  documents_total: number;
  documents_by_status: Array<{ status: DocumentStatus; count: number }>;
  recent_audit_events: Array<{
    id: string;
    document_id: string | null;
    action: string;
    actor: string;
    correlation_id: string;
    created_at: string;
  }>;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
    readonly correlationId?: string,
    readonly details: ErrorResponse["error"]["details"] = []
  ) {
    super(message);
  }
}

export class ApiClient {
  private token: string | null = null;

  constructor(readonly baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000") {}

  setToken(token: string | null): void {
    this.token = token;
  }

  async login(request: LoginRequest): Promise<string> {
    const response = await this.request<{ access_token: string }>("/api/v1/auth/login", {
      method: "POST",
      auth: false,
      json: {
        username: request.username,
        password: request.password ?? "securedox-demo",
        tenant_id: request.tenantId ?? "acme-lending"
      }
    });
    this.token = response.access_token;
    return response.access_token;
  }

  async uploadDocument(input: {
    documentType: string;
    filename: string;
    mimeType: string;
    content: Buffer;
    correlationId?: string;
  }): Promise<UploadResult> {
    const form = new FormData();
    form.append("document_type", input.documentType);
    form.append(
      "file",
      new Blob([new Uint8Array(input.content)], { type: input.mimeType }),
      input.filename
    );
    return this.request<UploadResult>("/api/v1/documents", {
      method: "POST",
      body: form,
      correlationId: input.correlationId
    });
  }

  async listDocuments(): Promise<DocumentSummary[]> {
    const page = await this.request<{ items: DocumentSummary[] }>("/api/v1/documents?limit=50");
    return page.items;
  }

  async getDocument(documentId: string): Promise<DocumentDetail> {
    return this.request<DocumentDetail>(`/api/v1/documents/${documentId}`);
  }

  async reviewDocument(
    documentId: string,
    input: {
      note: string;
      corrections?: Array<{ field_name: string; value: string; reason: string }>;
    }
  ): Promise<{
    id: string;
    status: DocumentStatus;
    needs_manual_review: boolean;
    corrections_applied: number;
  }> {
    return this.request(`/api/v1/documents/${documentId}/review`, {
      method: "PATCH",
      json: { note: input.note, corrections: input.corrections ?? [] }
    });
  }

  async submitDocument(documentId: string, note = "Submitted by smoke test"): Promise<void> {
    await this.request(`/api/v1/documents/${documentId}/submit`, {
      method: "POST",
      json: { note }
    });
  }

  async listAuditLogs(
    options: { documentId?: string; action?: string } = {}
  ): Promise<AuditEvent[]> {
    const params = new URLSearchParams();
    if (options.documentId) {
      params.set("document_id", options.documentId);
    }
    if (options.action) {
      params.set("action", options.action);
    }
    const query = params.toString();
    const page = await this.request<{ items: AuditEvent[] }>(
      `/api/v1/audit-logs${query ? `?${query}` : ""}`
    );
    return page.items;
  }

  async adminStatus(): Promise<AdminStatus> {
    return this.request<AdminStatus>("/api/v1/admin/status");
  }

  async request<T = unknown>(
    path: string,
    options: {
      method?: string;
      json?: unknown;
      body?: BodyInit;
      auth?: boolean;
      correlationId?: string;
      headers?: Record<string, string>;
    } = {}
  ): Promise<T> {
    const headers = new Headers(options.headers ?? {});
    if (options.json !== undefined) {
      headers.set("Content-Type", "application/json");
    }
    if (options.auth !== false && this.token) {
      headers.set("Authorization", `Bearer ${this.token}`);
    }
    if (options.correlationId) {
      headers.set("X-Correlation-ID", options.correlationId);
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.json !== undefined ? JSON.stringify(options.json) : options.body
    });
    if (!response.ok) {
      throw await this.toError(response);
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }

  private async toError(response: Response): Promise<ApiError> {
    try {
      const body = (await response.json()) as {
        error?: ErrorResponse["error"];
      };
      return new ApiError(
        body.error?.message ?? response.statusText,
        response.status,
        body.error?.code,
        body.error?.correlation_id,
        body.error?.details ?? []
      );
    } catch {
      return new ApiError(response.statusText, response.status);
    }
  }
}
