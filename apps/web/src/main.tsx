import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  CheckCircle2,
  FileUp,
  LayoutDashboard,
  LogIn,
  RefreshCw,
  Save,
  Send,
  ShieldCheck
} from "lucide-react";
import "./styles.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  import.meta.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000";

type Role = "admin" | "reviewer" | "uploader";
type DocumentStatus =
  | "RECEIVED"
  | "QUEUED"
  | "EXTRACTING"
  | "VALIDATING"
  | "REVIEW_REQUIRED"
  | "VALIDATED"
  | "REJECTED"
  | "FAILED"
  | "QUARANTINED";

type TokenResponse = {
  access_token: string;
};

type DocumentSummary = {
  id: string;
  document_type: string;
  status: DocumentStatus;
  original_filename: string;
  size_bytes: number;
  created_at: string;
  processed_at: string | null;
};

type ExtractedField = {
  field_name: string;
  value: string | null;
  display_value: string | null;
  confidence: number;
  source: string;
  is_pii: boolean;
  low_confidence: boolean;
};

type ValidationResult = {
  rule_id: string;
  field_name: string;
  status: "PASS" | "WARN" | "FAIL";
  severity: string;
  message: string;
  is_blocking: boolean;
};

type DocumentDetail = DocumentSummary & {
  mime_type: string;
  correlation_id: string;
  page_count: number | null;
  ocr_provider: string | null;
  rejection_reason: string | null;
  needs_manual_review: boolean;
  extracted_fields: ExtractedField[];
  validation_results: ValidationResult[];
};

type AdminStatus = {
  tenant_id: string;
  queue_depth: number;
  documents_total: number;
  documents_by_status: { status: DocumentStatus; count: number }[];
  recent_audit_events: {
    id: string;
    document_id: string | null;
    action: string;
    actor: string;
    created_at: string;
  }[];
};

type Page<T> = {
  items: T[];
};

type ApiError = {
  error?: {
    message?: string;
    code?: string;
  };
};

function statusTone(status: DocumentStatus): string {
  if (status === "VALIDATED") return "good";
  if (status === "REJECTED" || status === "FAILED" || status === "QUARANTINED") return "bad";
  if (status === "EXTRACTING" || status === "VALIDATING" || status === "REVIEW_REQUIRED") {
    return "busy";
  }
  return "plain";
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as ApiError;
    return body.error?.message ?? body.error?.code ?? response.statusText;
  } catch {
    return response.statusText;
  }
}

function App() {
  const [role, setRole] = useState<Role>("admin");
  const [tenantId, setTenantId] = useState("acme-lending");
  const [token, setToken] = useState("");
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [adminStatus, setAdminStatus] = useState<AdminStatus | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploadType, setUploadType] = useState("LOAN");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [corrections, setCorrections] = useState<Record<string, string>>({});
  const [reviewNote, setReviewNote] = useState("");

  const authHeaders = useMemo(
    () => ({
      Authorization: `Bearer ${token}`
    }),
    [token]
  );

  async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        ...(token ? authHeaders : {}),
        ...(init.headers ?? {})
      }
    });
    if (!response.ok) {
      throw new Error(await parseError(response));
    }
    return (await response.json()) as T;
  }

  async function login(event?: FormEvent) {
    event?.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const data = await api<TokenResponse>("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: role,
          password: "securedox-demo",
          tenant_id: tenantId
        })
      });
      setToken(data.access_token);
      setMessage(`Signed in as ${role}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  async function refresh(preferredDocumentId = selectedId) {
    if (!token) return;
    setBusy(true);
    setMessage("");
    try {
      const [docs, status] = await Promise.all([
        api<Page<DocumentSummary>>("/api/v1/documents?limit=25"),
        role === "admin"
          ? api<AdminStatus>("/api/v1/admin/status")
          : Promise.resolve<AdminStatus | null>(null)
      ]);
      setDocuments(docs.items);
      setAdminStatus(status);
      const nextId = preferredDocumentId || docs.items[0]?.id || "";
      setSelectedId(nextId);
      if (nextId) {
        await loadDetail(nextId);
      } else {
        setDetail(null);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Refresh failed");
    } finally {
      setBusy(false);
    }
  }

  async function loadDetail(id: string) {
    const next = await api<DocumentDetail>(`/api/v1/documents/${id}`);
    setSelectedId(id);
    setDetail(next);
    setCorrections(
      Object.fromEntries(
        next.extracted_fields.map((field) => [field.field_name, field.value ?? ""])
      )
    );
  }

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!uploadFile) return;
    setBusy(true);
    setMessage("");
    const form = new FormData();
    form.append("document_type", uploadType);
    form.append("file", uploadFile, uploadFile.name);
    try {
      const created = await api<{ id: string; status: DocumentStatus }>("/api/v1/documents", {
        method: "POST",
        body: form
      });
      setSelectedId(created.id);
      setMessage(`Upload accepted: ${created.status}`);
      await refresh(created.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveField(field: ExtractedField) {
    const value = corrections[field.field_name]?.trim();
    if (!detail || !value) return;
    setBusy(true);
    try {
      await api<ExtractedField>(`/api/v1/documents/${detail.id}/fields`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          field_name: field.field_name,
          value,
          reason: "Reviewed in phase 2 web app"
        })
      });
      await loadDetail(detail.id);
      setMessage(`${field.field_name} saved`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function submitReview() {
    if (!detail) return;
    setBusy(true);
    try {
      await api<{ submitted: boolean }>(`/api/v1/documents/${detail.id}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: reviewNote || null })
      });
      await refresh();
      setMessage("Review submitted");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Submit failed");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (token) {
      void refresh();
    }
  }, [token]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">SecureDox</p>
          <h1>Document Intake</h1>
        </div>
        <form className="auth-strip" onSubmit={login}>
          <select value={role} onChange={(event) => setRole(event.target.value as Role)}>
            <option value="admin">Admin</option>
            <option value="reviewer">Reviewer</option>
            <option value="uploader">Uploader</option>
          </select>
          <input value={tenantId} onChange={(event) => setTenantId(event.target.value)} />
          <button type="submit" disabled={busy}>
            <LogIn size={16} />
            Sign in
          </button>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={!token || busy}
            title="Refresh"
            aria-label="Refresh"
          >
            <RefreshCw size={16} />
          </button>
        </form>
      </header>

      {message ? <div className="notice">{message}</div> : null}

      <section className="workspace">
        <aside className="left-rail">
          <form className="upload-panel" onSubmit={upload}>
            <div className="section-title">
              <FileUp size={18} />
              <h2>Upload</h2>
            </div>
            <select value={uploadType} onChange={(event) => setUploadType(event.target.value)}>
              <option value="LOAN">Loan</option>
              <option value="INSURANCE">Insurance</option>
              <option value="MEDICAL">Medical</option>
              <option value="ONBOARDING">Onboarding</option>
            </select>
            <input
              type="file"
              accept="application/pdf,image/png,image/jpeg,image/tiff"
              onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
            />
            <button type="submit" disabled={!token || !uploadFile || busy}>
              <FileUp size={16} />
              Upload
            </button>
          </form>

          <div className="document-list">
            <div className="section-title">
              <Activity size={18} />
              <h2>Documents</h2>
            </div>
            {documents.map((document) => (
              <button
                className={`document-row ${selectedId === document.id ? "selected" : ""}`}
                key={document.id}
                type="button"
                onClick={() => void loadDetail(document.id)}
              >
                <span>{document.original_filename}</span>
                <span className={`pill ${statusTone(document.status)}`}>{document.status}</span>
              </button>
            ))}
          </div>
        </aside>

        <section className="review-pane">
          <div className="section-title">
            <ShieldCheck size={18} />
            <h2>Review</h2>
          </div>
          {detail ? (
            <>
              <div className="document-heading">
                <div>
                  <h3>{detail.original_filename}</h3>
                  <p>
                    {detail.document_type} / {formatBytes(detail.size_bytes)} /{" "}
                    {detail.ocr_provider ?? "pending OCR"}
                  </p>
                </div>
                <span className={`pill ${statusTone(detail.status)}`}>{detail.status}</span>
              </div>

              <div className="fields-grid">
                {detail.extracted_fields.map((field) => (
                  <div className="field-row" key={field.field_name}>
                    <div>
                      <strong>{field.field_name}</strong>
                      <span>{Math.round(field.confidence * 100)}% confidence</span>
                    </div>
                    <input
                      value={corrections[field.field_name] ?? ""}
                      placeholder={field.display_value ?? ""}
                      onChange={(event) =>
                        setCorrections((current) => ({
                          ...current,
                          [field.field_name]: event.target.value
                        }))
                      }
                    />
                    <button type="button" onClick={() => void saveField(field)} disabled={busy}>
                      <Save size={16} />
                    </button>
                  </div>
                ))}
              </div>

              <div className="validation-list">
                {detail.validation_results.map((result) => (
                  <div className="validation-row" key={result.rule_id}>
                    <span className={`pill ${result.status === "PASS" ? "good" : "bad"}`}>
                      {result.status}
                    </span>
                    <strong>{result.rule_id}</strong>
                    <span>{result.message}</span>
                  </div>
                ))}
              </div>

              <div className="submit-strip">
                <input
                  value={reviewNote}
                  onChange={(event) => setReviewNote(event.target.value)}
                  placeholder="Review note"
                />
                <button type="button" onClick={submitReview} disabled={busy}>
                  <Send size={16} />
                  Submit
                </button>
              </div>
            </>
          ) : (
            <div className="empty-state">No document selected</div>
          )}
        </section>

        <aside className="admin-pane">
          <div className="section-title">
            <LayoutDashboard size={18} />
            <h2>Status</h2>
          </div>
          {adminStatus ? (
            <>
              <div className="metric-grid">
                <div>
                  <span>Documents</span>
                  <strong>{adminStatus.documents_total}</strong>
                </div>
                <div>
                  <span>Queue</span>
                  <strong>{adminStatus.queue_depth}</strong>
                </div>
              </div>
              <div className="status-counts">
                {adminStatus.documents_by_status.map((item) => (
                  <div key={item.status}>
                    <span>{item.status}</span>
                    <strong>{item.count}</strong>
                  </div>
                ))}
              </div>
              <div className="audit-list">
                {adminStatus.recent_audit_events.map((event) => (
                  <div key={event.id}>
                    <CheckCircle2 size={15} />
                    <span>{event.action}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="empty-state">Admin sign-in required</div>
          )}
        </aside>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
