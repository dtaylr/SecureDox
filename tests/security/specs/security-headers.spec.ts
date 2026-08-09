import { expect, test } from "@playwright/test";

test("API responses include baseline security headers", async ({ request }) => {
  const response = await request.get("/health");

  expect(response.status()).toBe(200);
  expect(response.headers()["x-content-type-options"]).toBe("nosniff");
  expect(response.headers()["x-frame-options"]).toBe("DENY");
  expect(response.headers()["referrer-policy"]).toBe("no-referrer");
  expect(response.headers()["content-security-policy"]).toContain("default-src 'none'");
});
