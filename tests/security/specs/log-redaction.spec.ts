import { expect, test } from "@playwright/test";
import {
  ApiClient,
  DbClient,
  documentFixtureFactory,
  waitForAuditActions,
  waitForReviewReady
} from "@securedox/test-framework";

test("field correction audit log redacts sensitive values", async () => {
  const api = new ApiClient();
  const db = new DbClient();
  await api.login({ username: "admin" });

  try {
    const upload = await api.uploadDocument(
      documentFixtureFactory({ uniqueSuffix: `redaction-${Date.now()}` })
    );
    await waitForReviewReady(api, upload.id);

    await api.request(`/api/v1/documents/${upload.id}/fields`, {
      method: "PATCH",
      json: {
        field_name: "ssn",
        value: "999-99-9999",
        reason: "Security redaction test"
      }
    });

    const events = await waitForAuditActions(db, upload.id, ["FIELD_CORRECTED"]);
    const serializedDetails = JSON.stringify(events.map((event) => event.detail));
    expect(serializedDetails).not.toContain("999-99-9999");
    expect(serializedDetails).not.toMatch(/\d{3}-\d{2}-\d{4}/);
  } finally {
    await db.close();
  }
});
