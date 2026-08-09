import assert from "node:assert/strict";
import { ApiError, type DocumentDetail, type DocumentStatus } from "../clients/ApiClient.js";

export function assertStatus(document: DocumentDetail, statuses: DocumentStatus[]): void {
  assert.ok(
    statuses.includes(document.status),
    `Expected document ${document.id} to be ${statuses.join(", ")}, got ${document.status}`
  );
}

export function assertHasExtractedFields(document: DocumentDetail): void {
  assert.ok(document.extracted_fields.length > 0, "Expected OCR placeholder fields");
}

export function assertApiError(error: unknown, status: number, code?: string): void {
  assert.ok(error instanceof ApiError, "Expected ApiError");
  assert.equal(error.status, status);
  if (code) {
    assert.equal(error.code, code);
  }
}
