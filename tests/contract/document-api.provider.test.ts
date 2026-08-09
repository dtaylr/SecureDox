import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import {
  ApiClient,
  ApiError,
  correlationId,
  documentFixtureFactory,
  waitForReviewReady,
  type AuditEvent,
  type DocumentDetail
} from "../../packages/test-framework/src/index.js";

function assertDocumentStatusShape(document: DocumentDetail): void {
  assert.equal(typeof document.id, "string");
  assert.ok(
    [
      "RECEIVED",
      "QUEUED",
      "EXTRACTING",
      "VALIDATING",
      "REVIEW_REQUIRED",
      "VALIDATED",
      "REJECTED",
      "FAILED",
      "QUARANTINED"
    ].includes(document.status),
    `Unexpected status ${document.status}`
  );
  assert.equal(typeof document.needs_manual_review, "boolean");
  assert.ok(Array.isArray(document.extracted_fields));
  assert.ok(Array.isArray(document.validation_results));
}

function assertOcrConfidenceField(document: DocumentDetail): void {
  const field = document.extracted_fields.find((item) => item.field_name === "applicant_name");
  assert.ok(field, "Expected applicant_name OCR field");
  assert.equal(typeof field.confidence, "number");
  assert.ok(field.confidence >= 0 && field.confidence <= 1);
  assert.equal(typeof field.is_pii, "boolean");
}

async function assertValidationErrorStructure(api: ApiClient, documentId: string): Promise<void> {
  await assert.rejects(
    () => api.reviewDocument(documentId, { note: "no" }),
    (error: unknown) => {
      assert.ok(error instanceof ApiError, "Expected ApiError");
      assert.equal(error.status, 422);
      assert.equal(error.code, "VALIDATION_ERROR");
      assert.ok(error.correlationId);
      assert.ok(error.details.some((detail) => detail.field === "note"));
      return true;
    }
  );
}

function assertAuditEventShape(event: AuditEvent): void {
  assert.equal(typeof event.id, "string");
  assert.equal(typeof event.action, "string");
  assert.equal(typeof event.actor, "string");
  assert.equal(typeof event.correlation_id, "string");
  assert.equal(typeof event.created_at, "string");
  assert.equal(typeof event.detail, "object");
}

export async function runProviderContractTests(): Promise<void> {
  const api = new ApiClient();
  const health = await fetch(`${api.baseUrl}/health`);
  assert.equal(health.status, 200, "SecureDox API must be running for provider verification");

  await api.login({ username: "admin", tenantId: "acme-lending" });
  const fixture = documentFixtureFactory({
    uniqueSuffix: correlationId("contract-provider")
  });
  const upload = await api.uploadDocument(fixture);
  const document = await waitForReviewReady(api, upload.id);

  assertDocumentStatusShape(document);
  assertOcrConfidenceField(document);
  await assertValidationErrorStructure(api, upload.id);

  const auditEvents = await api.listAuditLogs({ documentId: upload.id });
  assert.ok(auditEvents.length > 0, "Expected at least one audit event");
  const firstAuditEvent = auditEvents.at(0);
  assert.ok(firstAuditEvent);
  assertAuditEventShape(firstAuditEvent);
}

const invokedDirectly =
  process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href;

if (invokedDirectly) {
  await runProviderContractTests();
}
