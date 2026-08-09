import { changedFilesFromArgs, readRepoFile, unique } from "./repo.ts";
import { logActivity } from "./activity.ts";

export type ToolDefinition = {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  run: (args: Record<string, unknown>) => unknown;
};

type RiskLevel = "P0" | "P1" | "P2";

const REVIEW_CHECKS = [
  "Asserts the business outcome, not only visible text.",
  "Validates persisted state when the feature writes data.",
  "Checks negative paths and validation failures.",
  "Proves auth or authorization behavior when tenant/user scope matters.",
  "Uses deterministic users, documents, and correlation IDs.",
  "Checks audit logs for regulated state changes.",
  "Avoids over-mocking the real production risk.",
  "Would fail before the bug or missing behavior is fixed."
];

const TOOL_INPUT_SCHEMA = {
  type: "object",
  additionalProperties: true
};

function withActivity(name: string, run: (args: Record<string, unknown>) => unknown) {
  return (args: Record<string, unknown>) => {
    try {
      const result = run(args);
      logActivity(name, args, "ok");
      return result;
    } catch (error) {
      logActivity(name, args, "error");
      throw error;
    }
  };
}

function textArg(args: Record<string, unknown>, ...keys: string[]): string {
  for (const key of keys) {
    const value = args[key];
    if (typeof value === "string") {
      return value;
    }
  }
  return "";
}

function routeRisk(method: string, path: string, changedFiles: string[] = []): {
  risk_level: RiskLevel;
  risk_factors: string[];
  required_tests: string[];
  release_gates: string[];
} {
  const route = `${method.toUpperCase()} ${path}`.trim();
  const riskFactors: string[] = [];
  const tests: string[] = [];
  const gates = ["api", "contract"];

  if (/auth|login|token/i.test(route)) {
    riskFactors.push("Authentication boundary");
    tests.push("tests/security/specs/auth.spec.ts", "tests/api/test_document_boundaries.py");
    gates.push("security");
  }
  if (/documents/i.test(route)) {
    riskFactors.push("Regulated document intake workflow");
    tests.push("tests/api/test_intake_smoke.py", "tests/db/test_integrity_boundaries.py");
    gates.push("db", "ocr");
  }
  if (/audit/i.test(route)) {
    riskFactors.push("Audit evidence and tenant-scoped records");
    tests.push("tests/api/test_document_boundaries.py", "tests/db/test_integrity_boundaries.py");
    gates.push("db", "security");
  }
  if (/submit|review|fields/i.test(route)) {
    riskFactors.push("Human review state transition");
    tests.push("tests/e2e/specs/intake-smoke.spec.ts", "tests/contract/document-api.provider.test.ts");
  }
  if (changedFiles.some((file) => /security|auth|gitleaks|semgrep|trivy|Dockerfile|workflow/.test(file))) {
    riskFactors.push("Security-sensitive files changed");
    gates.push("security-gates");
  }

  const level: RiskLevel =
    riskFactors.some((factor) => /Authentication|Audit|Security/.test(factor)) || /documents|audit/.test(path)
      ? "P0"
      : riskFactors.length > 0
        ? "P1"
        : "P2";

  return {
    risk_level: level,
    risk_factors: riskFactors.length ? riskFactors : ["No regulated boundary detected"],
    required_tests: unique(tests),
    release_gates: unique(gates)
  };
}

function detectChangedRoutes(args: Record<string, unknown>): unknown {
  const changedFiles = changedFilesFromArgs(args);
  const routeFiles = changedFiles.filter((file) => /apps\/api\/app\/api\/v1\/.*\.py$/.test(file));
  const routes = routeFiles.flatMap((file) => {
    const source = readRepoFile(file) ?? "";
    const matches = [...source.matchAll(/@router\.(get|post|patch|put|delete)\(\s*["']([^"']*)/g)];
    return matches.map((match) => ({
      file,
      method: (match[1] ?? "GET").toUpperCase(),
      path: match[2] ?? ""
    }));
  });
  return { changed_files: changedFiles, changed_route_files: routeFiles, routes };
}

function detectChangedApiContracts(args: Record<string, unknown>): unknown {
  const changedFiles = changedFilesFromArgs(args);
  const contractFiles = changedFiles.filter((file) =>
    /apps\/api\/app\/schemas|packages\/contracts|tests\/contract|openapi|apps\/api\/app\/api\/v1/.test(file)
  );
  return {
    changed_files: contractFiles,
    contract_risk: contractFiles.length > 0 ? "changed" : "unchanged",
    required_tests: contractFiles.length > 0 ? ["make test-contract", "make test-api"] : []
  };
}

function detectChangedDbSchema(args: Record<string, unknown>): unknown {
  const changedFiles = changedFilesFromArgs(args);
  const schemaFiles = changedFiles.filter((file) =>
    /alembic\/versions|apps\/api\/app\/models|packages\/shared\/python\/securedox_shared\/enums/.test(file)
  );
  return {
    changed_files: schemaFiles,
    schema_risk: schemaFiles.length > 0 ? "changed" : "unchanged",
    required_tests: schemaFiles.length > 0 ? ["make test-db", "make test-api"] : []
  };
}

function detectChangedSecuritySensitiveFiles(args: Record<string, unknown>): unknown {
  const changedFiles = changedFilesFromArgs(args);
  const securityFiles = changedFiles.filter((file) =>
    /auth|security|gitleaks|semgrep|trivy|Dockerfile|docker-compose|\.github\/workflows|nginx|dependencies|package\.json/.test(
      file
    )
  );
  return {
    changed_files: securityFiles,
    security_risk: securityFiles.length > 0 ? "changed" : "unchanged",
    required_gates: securityFiles.length > 0 ? ["make security", "make test-security", "yarn gate:security"] : []
  };
}

function suggestImpactedTests(args: Record<string, unknown>): unknown {
  const changedFiles = changedFilesFromArgs(args);
  const tests: string[] = [];
  if (changedFiles.some((file) => /apps\/api|packages\/shared\/python/.test(file))) {
    tests.push("make test-api", "make test-contract");
  }
  if (changedFiles.some((file) => /models|alembic|db|enums/.test(file))) {
    tests.push("make test-db");
  }
  if (changedFiles.some((file) => /worker|ocr|rules|test-documents/.test(file))) {
    tests.push("make test-ocr");
  }
  if (changedFiles.some((file) => /apps\/web|tests\/e2e/.test(file))) {
    tests.push("yarn test:e2e");
  }
  if (changedFiles.some((file) => /security|auth|Dockerfile|workflow|gitleaks|semgrep|trivy/.test(file))) {
    tests.push("make test-security", "make security");
  }
  if (changedFiles.some((file) => /observability|sre-runbooks|prometheus|grafana/.test(file))) {
    tests.push("make test-observability");
  }
  return { changed_files: changedFiles, impacted_tests: unique(tests) };
}

function suggestRequiredReleaseGates(args: Record<string, unknown>): unknown {
  const changedFiles = changedFilesFromArgs(args);
  const gates = ["yarn gate:release"];
  if (changedFiles.some((file) => /security|Dockerfile|workflow|gitleaks|semgrep|trivy|package\.json/.test(file))) {
    gates.push("yarn gate:security", "make security");
  }
  if (changedFiles.some((file) => /apps\/api|apps\/worker|packages\/shared|tests\/contract/.test(file))) {
    gates.push("make test-api", "make test-db", "make test-contract");
  }
  if (changedFiles.some((file) => /ocr|test-documents/.test(file))) {
    gates.push("make test-ocr");
  }
  return { changed_files: changedFiles, required_release_gates: unique(gates) };
}

function analyzeRouteRisk(args: Record<string, unknown>): unknown {
  const method = textArg(args, "method") || "GET";
  const path = textArg(args, "path", "route");
  return {
    route: `${method.toUpperCase()} ${path}`.trim(),
    ...routeRisk(method, path, changedFilesFromArgs(args))
  };
}

function generatePlaywrightTest(args: Record<string, unknown>): unknown {
  const scenario = textArg(args, "scenario", "name") || "generated intake scenario";
  const route = textArg(args, "route", "path") || "/api/v1/documents";
  const slug = scenario.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "generated";
  const includeDb = args.include_db_validation !== false && args.includeDbValidation !== false;
  const includeAudit = args.include_audit_validation !== false && args.includeAuditValidation !== false;
  const code = `import { expect, test } from "@playwright/test";
import { ApiClient, documentFixtureFactory, waitForReviewReady } from "@securedox/test-framework";

test("${scenario}", async () => {
  const api = new ApiClient();
  await api.login({ username: "admin", tenantId: "acme-lending" });

  const upload = await api.uploadDocument(documentFixtureFactory({
    uniqueSuffix: \`ai-${Date.now()}\`
  }));
  const document = await waitForReviewReady(api, upload.id);

  expect(document.id).toBe(upload.id);
  expect(["REVIEW_REQUIRED", "VALIDATED", "REJECTED"]).toContain(document.status);
  expect(document.extracted_fields.length).toBeGreaterThan(0);
${includeAudit ? "  const audit = await api.listAuditLogs({ documentId: upload.id });\n  expect(audit.map((event) => event.action)).toContain(\"DOCUMENT_UPLOADED\");" : ""}
${includeDb ? "  // Add DB validation with DbClient before merge if this scenario relies on persistence." : ""}
});`;

  return {
    file_path: `tests/e2e/specs/${slug}.generated.spec.ts`,
    route,
    code,
    requires_human_review: true,
    review_checklist: REVIEW_CHECKS,
    generated_test_review_manifest_entry: {
      test: `tests/e2e/specs/${slug}.generated.spec.ts`,
      requirement: textArg(args, "requirement", "requirement_id", "requirementId") || "unmapped",
      approved: false,
      reviewer: null,
      notes: "Generated by MCP Test Architect; complete checklist before merge."
    }
  };
}

function reviewTestForFalseConfidence(args: Record<string, unknown>): unknown {
  const code = textArg(args, "test_code", "testCode", "code");
  const findings: string[] = [];
  if (!/expect\s*\(/.test(code)) findings.push("No explicit assertion found.");
  if (/toBeVisible|toContainText|textContent/.test(code) && !/getDocument|DbClient|audit|api\./.test(code)) {
    findings.push("Mostly checks visible text; add API, DB, or audit assertions.");
  }
  if (!/401|403|404|rejects|UNAUTHORIZED|FORBIDDEN|NOT_FOUND|negative/i.test(code)) {
    findings.push("No negative or authorization boundary assertion detected.");
  }
  if (!/documentFixtureFactory|document_fixture|uniqueSuffix|correlation/i.test(code)) {
    findings.push("No deterministic document/correlation fixture detected.");
  }
  if (/mock|route\.fulfill|page\.route/.test(code) && !/audit|DbClient|getDocument/.test(code)) {
    findings.push("Potential over-mocking of the real service boundary.");
  }
  if (!/audit|Audit/.test(code)) findings.push("No audit-log assertion detected for regulated workflow.");
  const score = Math.max(0, 100 - findings.length * 15);
  return {
    false_confidence_score: score,
    risk: score >= 85 ? "low" : score >= 60 ? "medium" : "high",
    approved_for_merge: false,
    findings,
    must_fix_before_merge: findings.filter((finding) => /No explicit|over-mocking|authorization|audit/.test(finding))
  };
}

function suggestMissingAssertions(args: Record<string, unknown>): unknown {
  const review = reviewTestForFalseConfidence(args) as { findings: string[] };
  const suggestions = review.findings.map((finding) => {
    if (finding.includes("visible text")) return "Assert API response state and persisted DB row, not just UI text.";
    if (finding.includes("authorization")) return "Add an unauthenticated or cross-tenant request assertion.";
    if (finding.includes("audit")) return "Assert required audit events for upload, validation, review, or submit.";
    if (finding.includes("deterministic")) return "Use deterministic fixture factories and correlation IDs.";
    if (finding.includes("over-mocking")) return "Prefer the local API/worker stack over route mocking for boundary risks.";
    return "Add a direct business outcome assertion.";
  });
  return { missing_assertions: unique(suggestions) };
}

function mapTestToRequirement(args: Record<string, unknown>): unknown {
  const code = textArg(args, "test_code", "testCode", "code");
  const name = textArg(args, "test_name", "testName", "name");
  const text = `${name}\n${code}`.toLowerCase();
  const requirements = [];
  if (/upload|document/.test(text)) requirements.push("REQ-DOC-UPLOAD");
  if (/review|required|submit/.test(text)) requirements.push("REQ-DOC-REVIEW-SUBMIT");
  if (/audit/.test(text)) requirements.push("REQ-AUDIT-EVIDENCE");
  if (/unauth|forbidden|idor|tenant|authorization/.test(text)) requirements.push("REQ-AUTHZ-TENANT-ISOLATION");
  if (/ocr|confidence|extracted/.test(text)) requirements.push("REQ-OCR-VALIDATION");
  return {
    test_name: name || "unnamed",
    mapped_requirements: requirements.length ? requirements : ["REQ-UNMAPPED"],
    review_required: requirements.length === 0
  };
}

function summarizeReleaseRisk(args: Record<string, unknown>): unknown {
  const changedFiles = changedFilesFromArgs(args);
  const impacted = suggestImpactedTests({ changed_files: changedFiles }) as { impacted_tests: string[] };
  const gates = suggestRequiredReleaseGates({ changed_files: changedFiles }) as { required_release_gates: string[] };
  const security = detectChangedSecuritySensitiveFiles({ changed_files: changedFiles }) as {
    changed_files: string[];
  };
  const db = detectChangedDbSchema({ changed_files: changedFiles }) as { changed_files: string[] };
  const contracts = detectChangedApiContracts({ changed_files: changedFiles }) as { changed_files: string[] };
  const topRisk: RiskLevel = security.changed_files.length || db.changed_files.length || contracts.changed_files.length ? "P0" : "P1";
  return {
    risk_level: changedFiles.length === 0 ? "P2" : topRisk,
    changed_files: changedFiles,
    impacted_tests: impacted.impacted_tests,
    required_release_gates: gates.required_release_gates,
    release_summary: `${changedFiles.length} changed file(s); ${impacted.impacted_tests.length} impacted test command(s).`
  };
}

export const tools: ToolDefinition[] = [
  { name: "analyze_route_risk", description: "Risk-score an API route and return required tests/gates.", inputSchema: TOOL_INPUT_SCHEMA, run: withActivity("analyze_route_risk", analyzeRouteRisk) },
  { name: "generate_playwright_test", description: "Draft a Playwright test and human-review manifest entry.", inputSchema: TOOL_INPUT_SCHEMA, run: withActivity("generate_playwright_test", generatePlaywrightTest) },
  { name: "review_test_for_false_confidence", description: "Flag weak assertions and over-mocking in a generated test.", inputSchema: TOOL_INPUT_SCHEMA, run: withActivity("review_test_for_false_confidence", reviewTestForFalseConfidence) },
  { name: "suggest_missing_assertions", description: "Suggest missing assertions for a test body.", inputSchema: TOOL_INPUT_SCHEMA, run: withActivity("suggest_missing_assertions", suggestMissingAssertions) },
  { name: "map_test_to_requirement", description: "Map a test to regulated requirements.", inputSchema: TOOL_INPUT_SCHEMA, run: withActivity("map_test_to_requirement", mapTestToRequirement) },
  { name: "summarize_release_risk", description: "Summarize release risk from changed files.", inputSchema: TOOL_INPUT_SCHEMA, run: withActivity("summarize_release_risk", summarizeReleaseRisk) },
  { name: "detect_changed_routes", description: "Detect changed FastAPI route files and route decorators.", inputSchema: TOOL_INPUT_SCHEMA, run: withActivity("detect_changed_routes", detectChangedRoutes) },
  { name: "detect_changed_api_contracts", description: "Detect changed API schema/contract files.", inputSchema: TOOL_INPUT_SCHEMA, run: withActivity("detect_changed_api_contracts", detectChangedApiContracts) },
  { name: "detect_changed_db_schema", description: "Detect changed DB model or migration files.", inputSchema: TOOL_INPUT_SCHEMA, run: withActivity("detect_changed_db_schema", detectChangedDbSchema) },
  { name: "detect_changed_security_sensitive_files", description: "Detect auth/security/CI/container-sensitive changes.", inputSchema: TOOL_INPUT_SCHEMA, run: withActivity("detect_changed_security_sensitive_files", detectChangedSecuritySensitiveFiles) },
  { name: "suggest_impacted_tests", description: "Suggest tests impacted by changed files.", inputSchema: TOOL_INPUT_SCHEMA, run: withActivity("suggest_impacted_tests", suggestImpactedTests) },
  { name: "suggest_required_release_gates", description: "Suggest release gates required by changed files.", inputSchema: TOOL_INPUT_SCHEMA, run: withActivity("suggest_required_release_gates", suggestRequiredReleaseGates) }
];

export function callTool(name: string, args: Record<string, unknown>): unknown {
  const tool = tools.find((item) => item.name === name);
  if (!tool) {
    throw new Error(`Unknown MCP tool: ${name}`);
  }
  return tool.run(args);
}
