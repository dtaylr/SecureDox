import assert from "node:assert/strict";
import {
  apiContractDiff,
  classifyChanges,
  dbSchemaDiff,
  observabilityImpact,
  releaseGatesForFiles,
  routeMap,
  securityImpact,
  selectImpactedTests
} from "../../scripts/agents/lib/agent-utils.ts";

const files = [
  "apps/api/app/api/v1/documents.py",
  "apps/api/alembic/versions/20260809_demo.py",
  "apps/api/app/core/security.py",
  "apps/web/src/main.tsx",
  "observability/prometheus/alerts.yml"
];

const classification = classifyChanges(files);
assert.ok(classification.change_types.includes("api_contract_change"));
assert.ok(classification.change_types.includes("database_schema_change"));
assert.ok(classification.change_types.includes("auth_security_sensitive_change"));
assert.equal(classification.risk, "critical");

const impacted = selectImpactedTests(files);
assert.equal(impacted.risk, "critical");
assert.ok(impacted.required_checks.includes("contract-tests"));
assert.ok(impacted.recommended_reviewers.includes("security-reviewer"));

assert.equal(apiContractDiff(files).risk, "high");
assert.equal(dbSchemaDiff(files).risk, "high");
assert.equal(securityImpact(files).risk, "critical");
assert.equal(observabilityImpact(files).risk, "medium");
assert.ok(releaseGatesForFiles(files).required_gates.includes("release-readiness"));

const routes = routeMap(["apps/api/app/api/v1/documents.py"]);
assert.ok(routes.some((route) => route.method === "POST" && route.route === ""));

console.log("Agent helper script tests passed.");
