import { expect, test } from "@playwright/test";
import { ApiClient, ApiError, documentFixtureFactory } from "@securedox/test-framework";

test("upload gate rejects content that does not match declared PDF type", async () => {
  const api = new ApiClient();
  await api.login({ username: "admin" });
  const fixture = documentFixtureFactory({ uniqueSuffix: `bad-upload-${Date.now()}` });

  await expect(
    api.uploadDocument({
      documentType: fixture.documentType,
      filename: fixture.filename,
      mimeType: "application/pdf",
      content: Buffer.from("not really a pdf")
    })
  ).rejects.toMatchObject({
    status: 415,
    code: "UNSUPPORTED_MEDIA_TYPE"
  } satisfies Partial<ApiError>);
});
