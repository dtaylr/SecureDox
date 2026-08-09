import assert from "node:assert/strict";
import type { AuditEventRow, DocumentRow } from "../clients/DbClient.js";

export function assertDocumentPersisted(row: DocumentRow | null, expectedStatus?: string): void {
  assert.ok(row, "Expected document row to exist");
  if (expectedStatus) {
    assert.equal(row.status, expectedStatus);
  }
}

export function assertAuditSequence(events: AuditEventRow[], expectedActions: string[]): void {
  let cursor = 0;
  for (const event of events) {
    if (event.action === expectedActions[cursor]) {
      cursor += 1;
    }
  }
  assert.equal(cursor, expectedActions.length, `Missing ordered audit sequence: ${expectedActions}`);
}
