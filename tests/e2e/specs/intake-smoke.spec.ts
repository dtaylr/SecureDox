import { expect, test } from "@playwright/test";
import {
  ApiClient,
  DbClient,
  assertAuditActions,
  documentFixtureFactory,
  waitForAuditActions,
  waitForDocumentStatus,
  waitForReviewReady
} from "@securedox/test-framework";

test("user can upload, review, submit, and produce audit evidence", async ({ page }) => {
  const api = new ApiClient();
  const db = new DbClient();
  const fixture = documentFixtureFactory({
    uniqueSuffix: `e2e-${test.info().workerIndex}-${Date.now()}`
  });

  try {
    await api.login({ username: "admin" });
    await page.goto("/");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("Signed in as admin")).toBeVisible();

    await page.locator('input[type="file"]').setInputFiles({
      name: fixture.filename,
      mimeType: fixture.mimeType,
      buffer: fixture.content
    });
    await page.getByRole("button", { name: "Upload" }).click();
    await expect(page.getByText(/Upload accepted:/)).toBeVisible();

    const uploaded = (await api.listDocuments()).find(
      (document) => document.original_filename === fixture.filename
    );
    expect(uploaded, "uploaded document appears in API list").toBeTruthy();

    await waitForDocumentStatus(api, uploaded!.id, ["QUEUED", "EXTRACTING", "VALIDATING", "VALIDATED"]);
    const reviewed = await waitForReviewReady(api, uploaded!.id);
    expect(reviewed.extracted_fields.length).toBeGreaterThan(0);

    await page.getByRole("button", { name: "Refresh" }).click();
    await page.getByText(fixture.filename).click();
    await expect(page.getByText("applicant_name")).toBeVisible();
    await page.getByPlaceholder("Review note").fill("Playwright smoke review");
    await page.getByRole("button", { name: "Submit" }).click();
    await expect(page.getByText("Review submitted")).toBeVisible();

    const events = await waitForAuditActions(db, uploaded!.id, [
      "DOCUMENT_UPLOADED",
      "DOCUMENT_QUEUED",
      "EXTRACTION_COMPLETED",
      "VALIDATION_COMPLETED",
      "DOCUMENT_SUBMITTED"
    ]);
    assertAuditActions(events, ["DOCUMENT_UPLOADED", "DOCUMENT_SUBMITTED"]);
  } finally {
    await db.close();
  }
});
