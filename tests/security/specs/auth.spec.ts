import { expect, test } from "@playwright/test";
import { documentFixtureFactory } from "@securedox/test-framework";

test("unauthenticated user cannot upload", async ({ request }) => {
  const fixture = documentFixtureFactory({ uniqueSuffix: `auth-${Date.now()}` });

  const response = await request.post("/api/v1/documents", {
    multipart: {
      document_type: fixture.documentType,
      file: {
        name: fixture.filename,
        mimeType: fixture.mimeType,
        buffer: fixture.content
      }
    }
  });

  expect(response.status()).toBe(401);
  expect((await response.json()).error.code).toBe("UNAUTHORIZED");
});
