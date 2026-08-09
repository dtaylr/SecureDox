import assert from "node:assert/strict";
import { ApiError } from "../clients/ApiClient.js";

export function assertUnauthorized(error: unknown): void {
  assert.ok(error instanceof ApiError, "Expected API authorization failure");
  assert.equal(error.status, 401);
  assert.equal(error.code, "UNAUTHORIZED");
}

export function assertNoPiiInAuditDetail(detail: Record<string, unknown>): void {
  const serialized = JSON.stringify(detail);
  assert.ok(!/\d{3}-\d{2}-\d{4}/.test(serialized), "Audit detail contains SSN-shaped PII");
}
