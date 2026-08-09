import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

type ReleaseDecision = "GO" | "NO-GO";

type ReleaseReadiness = {
  release_decision: ReleaseDecision;
  generated_at: string;
  thresholds: {
    max_flake_rate: string;
    max_p95_latency_ms: number;
    max_error_rate: string;
    min_critical_path_pass_rate: string;
    max_ocr_p95_latency_ms: number;
  };
  quality: {
    critical_path_pass_rate: string;
    flake_rate: string;
    contract_tests: "passed" | "failed" | "missing";
    critical_path_tests: "passed" | "failed" | "missing";
    total_tests: number;
    failed_tests: number;
  };
  security: {
    secrets_found: number;
    sast_blockers: number;
    critical_dependency_vulns: number;
    critical_container_vulns: number;
    sbom_generated: boolean;
    idor_tests: "passed" | "failed" | "missing";
    sensitive_log_leakage: "not_detected" | "detected" | "missing";
  };
  reliability: {
    p95_upload_latency_ms: number | null;
    error_rate: string;
    audit_log_validation: "passed" | "failed" | "missing";
    ocr_p95_latency_ms: number | null;
    ocr_quality: "passed" | "failed" | "missing";
  };
  data_integrity: {
    db_smoke: "passed" | "failed" | "missing";
    audit_sequence: "passed" | "failed" | "missing";
  };
  ai_generated_tests: {
    unapproved_tests: number;
    status: "passed" | "failed";
  };
  blockers: string[];
  warnings: string[];
  evidence: Record<string, string>;
};

type TestSummary = {
  status: "passed" | "failed" | "missing";
  total: number;
  failed: number;
  skipped: number;
};

const outputPath = argValue("--output") ?? "reports/release-readiness.json";
const prometheusOutputPath = argValue("--prometheus-output") ?? "reports/release-readiness.prom";
const noFail = process.argv.includes("--no-fail");

const thresholds = {
  maxFlakeRate: envNumber("GATE_MAX_FLAKE_RATE", 2.0),
  maxP95LatencyMs: envNumber("GATE_MAX_P95_MS", 800),
  maxOcrP95LatencyMs: envNumber("GATE_MAX_OCR_P95_MS", 5_000),
  maxErrorRate: envNumber("GATE_MAX_ERROR_RATE", 1.0),
  minCriticalPathPassRate: envNumber("GATE_MIN_CRITICAL_PATH_PASS_RATE", 100)
};

const evidence = {
  junitApi: "reports/junit-api.xml",
  junitDb: "reports/junit-db.xml",
  junitSecurity: "reports/junit-security.xml",
  junitOcr: "reports/junit-ocr.xml",
  junitContract: "reports/junit-contract.xml",
  playwrightE2e: "tests/reports/playwright-results.json",
  playwrightSecurity: "tests/reports/security-playwright-results.json",
  gitleaks: "reports/gitleaks.sarif",
  semgrep: "reports/semgrep.sarif",
  trivyFs: "reports/trivy-fs.json",
  trivyImages: "reports/trivy-images.json",
  sbomCycloneDx: "security/sbom/securedox-source.cdx.json",
  sbomSpdx: "security/sbom/securedox-source.spdx.json",
  performance: "reports/performance-summary.json",
  ocrQuality: "tests/reports/ocr-quality-summary.json",
  flake: "reports/flake-summary.json",
  audit: "tests/reports/api-smoke.json"
};

const api = readJUnit(evidence.junitApi);
const db = readJUnit(evidence.junitDb);
const securityPy = readJUnit(evidence.junitSecurity);
const ocr = readJUnit(evidence.junitOcr);
const contract = readJUnit(evidence.junitContract);
const e2e = readPlaywright(evidence.playwrightE2e);
const securityTs = readPlaywright(evidence.playwrightSecurity);

const criticalTotals = sumTests(api, e2e, ocr);
const criticalPassRate =
  criticalTotals.total === 0
    ? null
    : ((criticalTotals.total - criticalTotals.failed) / criticalTotals.total) * 100;

const flakeRate = readFlakeRate(evidence.flake);
const performance = readPerformance(evidence.performance);
const ocrQuality = readOcrQuality(evidence.ocrQuality);
const secretsFound = countSarifResults(evidence.gitleaks);
const sastBlockers = countSarifResults(evidence.semgrep, ["error"]);
const dependencyCriticals = countTrivyCriticals(evidence.trivyFs);
const containerCriticals = countTrivyCriticals(evidence.trivyImages);
const sbomGenerated = existsAndNonEmpty(evidence.sbomCycloneDx) && existsAndNonEmpty(evidence.sbomSpdx);
const unapprovedGeneratedTests = countUnapprovedGeneratedTests();
const idorStatus = specStatus(evidence.playwrightSecurity, "authorization-idor");
const logRedactionStatus = specStatus(evidence.playwrightSecurity, "log-redaction");
const uploadValidationStatus = specStatus(evidence.playwrightSecurity, "upload-validation");
const auditReport = readJson<{ audit_actions?: string[] }>(evidence.audit);
const auditSequenceStatus = auditReport
  ? auditReport.audit_actions?.includes("DOCUMENT_UPLOADED") &&
    auditReport.audit_actions?.includes("DOCUMENT_SUBMITTED")
    ? "passed"
    : "failed"
  : api.status === "missing"
    ? "missing"
    : "passed";

const blockers: string[] = [];
const warnings: string[] = [];

blockOn(api.status === "failed" || e2e.status === "failed", "Critical path test failed");
blockOn(criticalPassRate === null, "Critical path test evidence is missing");
blockOn(
  criticalPassRate !== null && criticalPassRate < thresholds.minCriticalPathPassRate,
  `Critical path pass rate is below ${thresholds.minCriticalPathPassRate}%`
);
blockOn(contract.status !== "passed", "Contract tests are not passing");
blockOn(ocr.status !== "passed", "OCR validation tests are not passing");
blockOn(idorStatus !== "passed", "IDOR/security access test is not passing");
blockOn(uploadValidationStatus !== "passed", "Upload validation security test is not passing");
blockOn(logRedactionStatus === "failed", "Sensitive log leakage is detected");
blockOn(logRedactionStatus === "missing", "Sensitive log redaction evidence is missing");
blockOn(!existsAndNonEmpty(evidence.gitleaks), "Secret scan evidence is missing");
blockOn(!existsAndNonEmpty(evidence.semgrep), "SAST evidence is missing");
blockOn(!existsAndNonEmpty(evidence.trivyFs), "Dependency/container filesystem scan evidence is missing");
blockOn(!existsAndNonEmpty(evidence.trivyImages), "Container image scan evidence is missing");
blockOn(secretsFound > 0, `${secretsFound} secret finding(s) detected`);
blockOn(sastBlockers > 0, `${sastBlockers} SAST blocker(s) detected`);
blockOn(dependencyCriticals > 0, `${dependencyCriticals} critical dependency vulnerability finding(s)`);
blockOn(containerCriticals > 0, `${containerCriticals} critical container vulnerability finding(s)`);
blockOn(!sbomGenerated, "SBOM is missing");
if (
  performance.p95UploadLatencyMs !== null &&
  performance.p95UploadLatencyMs > thresholds.maxP95LatencyMs
) {
  blockOn(
    true,
    `p95 upload latency ${performance.p95UploadLatencyMs}ms exceeds ${thresholds.maxP95LatencyMs}ms`
  );
}
if (
  performance.errorRatePercent !== null &&
  performance.errorRatePercent > thresholds.maxErrorRate
) {
  blockOn(
    true,
    `Error rate ${formatPercent(performance.errorRatePercent)} exceeds ${formatPercent(thresholds.maxErrorRate)}`
  );
}
blockOn(flakeRate !== null && flakeRate > thresholds.maxFlakeRate, "Flake rate exceeds threshold");
blockOn(
  ocrQuality.p95OcrLatencyMs !== null &&
    ocrQuality.p95OcrLatencyMs > thresholds.maxOcrP95LatencyMs,
  `OCR p95 latency ${ocrQuality.p95OcrLatencyMs}ms exceeds ${thresholds.maxOcrP95LatencyMs}ms`
);
blockOn(ocrQuality.status === "failed", "OCR quality validation failed");
blockOn(db.status === "failed", "DB/data integrity smoke test failed");
blockOn(auditSequenceStatus !== "passed", "Audit log validation failed or is missing");
blockOn(unapprovedGeneratedTests > 0, `${unapprovedGeneratedTests} AI-generated test(s) lack review approval`);

warnOn(securityPy.status === "missing", "Python security smoke evidence is missing");
warnOn(performance.p95UploadLatencyMs === null, "Performance evidence is missing");
warnOn(ocrQuality.status === "missing", "OCR quality evidence is missing");
warnOn(flakeRate === null, "Flake-rate evidence is missing");

const readiness: ReleaseReadiness = {
  release_decision: blockers.length > 0 ? "NO-GO" : "GO",
  generated_at: new Date().toISOString(),
  thresholds: {
    max_flake_rate: formatPercent(thresholds.maxFlakeRate),
    max_p95_latency_ms: thresholds.maxP95LatencyMs,
    max_error_rate: formatPercent(thresholds.maxErrorRate),
    min_critical_path_pass_rate: formatPercent(thresholds.minCriticalPathPassRate),
    max_ocr_p95_latency_ms: thresholds.maxOcrP95LatencyMs
  },
  quality: {
    critical_path_pass_rate: criticalPassRate === null ? "missing" : formatPercent(criticalPassRate),
    flake_rate: flakeRate === null ? "missing" : formatPercent(flakeRate),
    contract_tests: contract.status,
    critical_path_tests: summarizeStatus(api, e2e, ocr),
    total_tests: criticalTotals.total,
    failed_tests: criticalTotals.failed
  },
  security: {
    secrets_found: secretsFound,
    sast_blockers: sastBlockers,
    critical_dependency_vulns: dependencyCriticals,
    critical_container_vulns: containerCriticals,
    sbom_generated: sbomGenerated,
    idor_tests: idorStatus,
    sensitive_log_leakage:
      logRedactionStatus === "passed"
        ? "not_detected"
        : logRedactionStatus === "failed"
          ? "detected"
          : "missing"
  },
  reliability: {
    p95_upload_latency_ms: performance.p95UploadLatencyMs,
    error_rate: performance.errorRatePercent === null ? "missing" : formatPercent(performance.errorRatePercent),
    audit_log_validation: auditSequenceStatus,
    ocr_p95_latency_ms: ocrQuality.p95OcrLatencyMs,
    ocr_quality: ocrQuality.status
  },
  data_integrity: {
    db_smoke: db.status,
    audit_sequence: auditSequenceStatus
  },
  ai_generated_tests: {
    unapproved_tests: unapprovedGeneratedTests,
    status: unapprovedGeneratedTests === 0 ? "passed" : "failed"
  },
  blockers,
  warnings,
  evidence
};

mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, `${JSON.stringify(readiness, null, 2)}\n`);
writePrometheusEvidence(prometheusOutputPath, readiness, {
  criticalPassRate,
  flakeRate,
  blockerGates: blockers.map(classifyBlocker)
});
console.log(JSON.stringify(readiness, null, 2));

if (readiness.release_decision === "NO-GO" && !noFail) {
  process.exit(1);
}

function readJUnit(path: string): TestSummary {
  if (!existsAndNonEmpty(path)) {
    return { status: "missing", total: 0, failed: 0, skipped: 0 };
  }
  const xml = readFileSync(path, "utf8");
  const tests = numberAttr(xml, "tests");
  const failures = numberAttr(xml, "failures");
  const errors = numberAttr(xml, "errors");
  const skipped = numberAttr(xml, "skipped");
  const failed = failures + errors;
  return { status: failed > 0 ? "failed" : "passed", total: tests, failed, skipped };
}

function readPlaywright(path: string): TestSummary {
  const report = readJson<{ stats?: { expected?: number; unexpected?: number; skipped?: number } }>(path);
  if (!report?.stats) {
    return { status: "missing", total: 0, failed: 0, skipped: 0 };
  }
  const passed = report.stats.expected ?? 0;
  const failed = report.stats.unexpected ?? 0;
  const skipped = report.stats.skipped ?? 0;
  return { status: failed > 0 ? "failed" : "passed", total: passed + failed + skipped, failed, skipped };
}

function specStatus(path: string, specNamePart: string): "passed" | "failed" | "missing" {
  const report = readJson<{ suites?: unknown[] }>(path);
  if (!report) {
    return "missing";
  }
  const specs = JSON.stringify(report)
    .split('"title"')
    .filter((chunk) => chunk.includes(specNamePart));
  if (specs.length === 0) {
    return "missing";
  }
  return specs.some((chunk) => chunk.includes('"unexpected"') || chunk.includes('"failed"'))
    ? "failed"
    : "passed";
}

function readPerformance(path: string): {
  p95UploadLatencyMs: number | null;
  errorRatePercent: number | null;
} {
  const report = readJson<{
    p95_upload_latency_ms?: number;
    p95UploadLatencyMs?: number;
    error_rate?: string | number;
    errorRatePercent?: number;
  }>(path);
  if (!report) {
    return { p95UploadLatencyMs: null, errorRatePercent: null };
  }
  return {
    p95UploadLatencyMs: report.p95_upload_latency_ms ?? report.p95UploadLatencyMs ?? null,
    errorRatePercent: parsePercent(report.error_rate ?? report.errorRatePercent)
  };
}

function readFlakeRate(path: string): number | null {
  const report = readJson<{ flake_rate?: string | number; flakeRatePercent?: number }>(path);
  if (!report) {
    return null;
  }
  return parsePercent(report.flake_rate ?? report.flakeRatePercent);
}

function readOcrQuality(path: string): {
  p95OcrLatencyMs: number | null;
  status: "passed" | "failed" | "missing";
} {
  const report = readJson<{ p95_ocr_latency_ms?: number; status?: string }>(path);
  if (!report) {
    return { p95OcrLatencyMs: null, status: "missing" };
  }
  return {
    p95OcrLatencyMs: report.p95_ocr_latency_ms ?? null,
    status: report.status === "passed" ? "passed" : "failed"
  };
}

function countSarifResults(path: string, levels?: string[]): number {
  const sarif = readJson<{ runs?: Array<{ results?: Array<{ level?: string }> }> }>(path);
  if (!sarif) {
    return 0;
  }
  return (
    sarif.runs?.flatMap((run) => run.results ?? []).filter((result) =>
      levels ? levels.includes((result.level ?? "").toLowerCase()) : true
    ).length ?? 0
  );
}

function countTrivyCriticals(path: string): number {
  const report = readJson<{ Results?: Array<{ Vulnerabilities?: Array<{ Severity?: string }> }> }>(path);
  if (!report) {
    return 0;
  }
  return (
    report.Results?.flatMap((result) => result.Vulnerabilities ?? []).filter(
      (finding) => finding.Severity === "CRITICAL"
    ).length ?? 0
  );
}

function countUnapprovedGeneratedTests(): number {
  const manifest = readJson<{ tests?: Array<{ approved?: boolean }> }>(
    "tests/reports/generated-test-review.json"
  );
  if (!manifest) {
    return 0;
  }
  return manifest.tests?.filter((test) => !test.approved).length ?? 0;
}

function readJson<T>(path: string): T | null {
  if (!existsAndNonEmpty(path)) {
    return null;
  }
  try {
    return JSON.parse(readFileSync(path, "utf8")) as T;
  } catch {
    return null;
  }
}

function existsAndNonEmpty(path: string): boolean {
  return existsSync(path) && readFileSync(path, "utf8").trim().length > 0;
}

function numberAttr(xml: string, attr: string): number {
  const match = xml.match(new RegExp(`${attr}="(\\d+)"`));
  return match ? Number(match[1]) : 0;
}

function sumTests(...summaries: TestSummary[]): { total: number; failed: number } {
  return {
    total: summaries.reduce((total, summary) => total + summary.total, 0),
    failed: summaries.reduce((total, summary) => total + summary.failed, 0)
  };
}

function summarizeStatus(...summaries: TestSummary[]): "passed" | "failed" | "missing" {
  if (summaries.some((summary) => summary.status === "failed")) {
    return "failed";
  }
  if (summaries.some((summary) => summary.status === "missing")) {
    return "missing";
  }
  return "passed";
}

function parsePercent(value: string | number | undefined): number | null {
  if (value === undefined) {
    return null;
  }
  if (typeof value === "number") {
    return value;
  }
  const parsed = Number(value.replace("%", ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function formatPercent(value: number): string {
  return `${Number.isInteger(value) ? value : value.toFixed(1)}%`;
}

function envNumber(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) {
    return fallback;
  }
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function argValue(name: string): string | null {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] ?? null : null;
}

function blockOn(condition: boolean, message: string): void {
  if (condition) {
    blockers.push(message);
  }
}

function warnOn(condition: boolean, message: string): void {
  if (condition) {
    warnings.push(message);
  }
}

function writePrometheusEvidence(
  path: string,
  readiness: ReleaseReadiness,
  values: {
    criticalPassRate: number | null;
    flakeRate: number | null;
    blockerGates: string[];
  }
): void {
  mkdirSync(dirname(path), { recursive: true });
  const gateCounts = values.blockerGates.reduce<Record<string, number>>((counts, gate) => {
    counts[gate] = (counts[gate] ?? 0) + 1;
    return counts;
  }, {});
  const lines = [
    "# HELP critical_path_pass_rate Most recent critical path pass rate as a ratio.",
    "# TYPE critical_path_pass_rate gauge",
    `critical_path_pass_rate ${values.criticalPassRate === null ? 0 : values.criticalPassRate / 100}`,
    "# HELP test_flake_rate Most recent observed test flake rate as a ratio.",
    "# TYPE test_flake_rate gauge",
    `test_flake_rate ${values.flakeRate === null ? 0 : values.flakeRate / 100}`,
    "# HELP release_gate_failures_total Release gate failures by gate category.",
    "# TYPE release_gate_failures_total counter",
    ...Object.entries(gateCounts).map(
      ([gate, count]) => `release_gate_failures_total{gate="${escapePromLabel(gate)}"} ${count}`
    ),
    "# HELP release_readiness_decision Current release decision, 1 for GO and 0 for NO-GO.",
    "# TYPE release_readiness_decision gauge",
    `release_readiness_decision ${readiness.release_decision === "GO" ? 1 : 0}`
  ];
  writeFileSync(path, `${lines.join("\n")}\n`);
}

function classifyBlocker(blocker: string): string {
  const text = blocker.toLowerCase();
  if (
    text.includes("secret") ||
    text.includes("sast") ||
    text.includes("security") ||
    text.includes("vulnerability") ||
    text.includes("sbom") ||
    text.includes("idor")
  ) {
    return "security";
  }
  if (text.includes("latency") || text.includes("error rate") || text.includes("ocr")) {
    return "reliability";
  }
  if (text.includes("db") || text.includes("audit") || text.includes("data")) {
    return "data_integrity";
  }
  if (text.includes("generated test") || text.includes("ai-generated")) {
    return "ai_generated_tests";
  }
  return "quality";
}

function escapePromLabel(value: string): string {
  return value.replaceAll("\\", "\\\\").replaceAll('"', '\\"').replaceAll("\n", "\\n");
}
