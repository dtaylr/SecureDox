import type { AuditEventRow, DbClient } from "../clients/DbClient.js";
import { retryUntil, type RetryOptions } from "./retry.helper.js";

export async function waitForAuditActions(
  db: DbClient,
  documentId: string,
  expectedActions: string[],
  options: RetryOptions = {}
): Promise<AuditEventRow[]> {
  return retryUntil(
    () => db.auditEventsForDocument(documentId),
    (events) => expectedActions.every((action) => events.some((event) => event.action === action)),
    {
      description: `audit actions ${expectedActions.join(", ")}`,
      timeoutMs: 30_000,
      ...options
    }
  );
}

export function assertAuditActions(events: AuditEventRow[], expectedActions: string[]): void {
  const actual = new Set(events.map((event) => event.action));
  const missing = expectedActions.filter((action) => !actual.has(action));
  if (missing.length > 0) {
    throw new Error(`Missing audit actions: ${missing.join(", ")}`);
  }
}
