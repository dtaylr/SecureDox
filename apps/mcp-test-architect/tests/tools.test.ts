import assert from "node:assert/strict";
import { callTool, tools } from "../src/tools.ts";

const requiredTools = [
  "analyze_route_risk",
  "generate_playwright_test",
  "review_test_for_false_confidence",
  "suggest_missing_assertions",
  "map_test_to_requirement",
  "summarize_release_risk",
  "detect_changed_routes",
  "detect_changed_api_contracts",
  "detect_changed_db_schema",
  "detect_changed_security_sensitive_files",
  "suggest_impacted_tests",
  "suggest_required_release_gates"
];

function run(): void {
  assert.deepEqual(
    tools.map((tool) => tool.name).sort(),
    [...requiredTools].sort()
  );

  const routeRisk = callTool("analyze_route_risk", {
    method: "POST",
    path: "/api/v1/documents"
  }) as { risk_level: string; required_tests: string[] };
  assert.equal(routeRisk.risk_level, "P0");
  assert.ok(routeRisk.required_tests.some((test) => test.includes("test_intake_smoke")));

  const generated = callTool("generate_playwright_test", {
    scenario: "user can upload document with audit evidence",
    requirement_id: "REQ-DOC-UPLOAD"
  }) as {
    code: string;
    requires_human_review: boolean;
    generated_test_review_manifest_entry: { approved: boolean };
  };
  assert.equal(generated.requires_human_review, true);
  assert.equal(generated.generated_test_review_manifest_entry.approved, false);
  assert.match(generated.code, /DOCUMENT_UPLOADED/);

  const weakReview = callTool("review_test_for_false_confidence", {
    test_code: "test('weak', async ({ page }) => { await expect(page.getByText('Done')).toBeVisible(); });"
  }) as { risk: string; findings: string[]; approved_for_merge: boolean };
  assert.equal(weakReview.approved_for_merge, false);
  assert.equal(weakReview.risk, "high");
  assert.ok(weakReview.findings.some((finding) => finding.includes("visible text")));

  const mapped = callTool("map_test_to_requirement", {
    test_name: "cross tenant IDOR audit test",
    test_code: "expect(error.code).toBe('NOT_FOUND'); expect(audit).toContain('DOCUMENT_UPLOADED');"
  }) as { mapped_requirements: string[] };
  assert.ok(mapped.mapped_requirements.includes("REQ-AUTHZ-TENANT-ISOLATION"));
  assert.ok(mapped.mapped_requirements.includes("REQ-AUDIT-EVIDENCE"));

  const impacted = callTool("suggest_impacted_tests", {
    changed_files: ["apps/api/app/api/v1/documents.py", "apps/api/alembic/versions/20260809_demo.py"]
  }) as { impacted_tests: string[] };
  assert.ok(impacted.impacted_tests.includes("make test-api"));
  assert.ok(impacted.impacted_tests.includes("make test-db"));

  const gates = callTool("suggest_required_release_gates", {
    changed_files: ["apps/api/app/core/security.py", "apps/api/Dockerfile"]
  }) as { required_release_gates: string[] };
  assert.ok(gates.required_release_gates.includes("yarn gate:security"));

  console.log(`MCP Test Architect tool tests passed (${requiredTools.length} tools).`);
}

run();
