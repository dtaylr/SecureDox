import { expect, test } from "@playwright/test";
import { ApiClient } from "@securedox/test-framework";

test("validation errors use the standard envelope and correlation id", async ({ request }) => {
  const api = new ApiClient();
  const token = await api.login({ username: "admin" });
  const correlationId = `sec-error-${Date.now()}`;

  const response = await request.get("/api/v1/documents/not-a-uuid", {
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Correlation-ID": correlationId
    }
  });
  const body = await response.json();

  expect(response.status()).toBe(422);
  expect(response.headers()["x-correlation-id"]).toBe(correlationId);
  expect(body.error.code).toBe("VALIDATION_ERROR");
  expect(body.error.correlation_id).toBe(correlationId);
  expect(JSON.stringify(body)).not.toContain("Traceback");
});
