import { expect, test } from "@playwright/test";
import {
  ApiClient,
  ApiError,
  documentFixtureFactory,
  waitForReviewReady
} from "@securedox/test-framework";

test("cross-tenant document access is hidden", async () => {
  const acme = new ApiClient();
  await acme.login({ username: "admin", tenantId: "acme-lending" });
  const upload = await acme.uploadDocument(
    documentFixtureFactory({ uniqueSuffix: `idor-${Date.now()}` })
  );
  await waitForReviewReady(acme, upload.id);

  const northwind = new ApiClient();
  await northwind.login({ username: "admin", tenantId: "northwind-health" });

  await expect(northwind.getDocument(upload.id)).rejects.toMatchObject({
    status: 404,
    code: "NOT_FOUND"
  } satisfies Partial<ApiError>);
});
