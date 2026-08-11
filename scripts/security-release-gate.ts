import { existsSync, readFileSync } from "node:fs";

type GateResult = {
  name: string;
  passed: boolean;
  reason?: string;
};

const gates: GateResult[] = [
  requireFile("secrets", "reports/gitleaks.sarif"),
  requireFile("sast", "reports/semgrep.sarif"),
  requireFile("sca", "reports/trivy-fs.json"),
  requireFile("containers", "reports/trivy-images.json"),
  requireFile("sbom-cyclonedx", "security/sbom/securedox-source.cdx.json"),
  requireFile("sbom-spdx", "security/sbom/securedox-source.spdx.json"),
];

if (existsSync("reports/trivy-fs.json")) {
  gates.push(
    assertNoCriticalTrivyFindings("trivy-fs-critical", "reports/trivy-fs.json"),
  );
}
if (existsSync("reports/trivy-images.json")) {
  gates.push(
    assertNoCriticalTrivyFindings(
      "trivy-images-critical",
      "reports/trivy-images.json",
    ),
  );
}

for (const gate of gates) {
  const prefix = gate.passed ? "PASS" : "FAIL";
  console.log(
    `${prefix} ${gate.name}${gate.reason ? ` - ${gate.reason}` : ""}`,
  );
}

if (gates.some((gate) => !gate.passed)) {
  process.exit(1);
}

function requireFile(name: string, path: string): GateResult {
  if (!existsSync(path)) {
    return { name, passed: false, reason: `${path} is missing` };
  }
  if (readFileSync(path, "utf8").trim().length === 0) {
    return { name, passed: false, reason: `${path} is empty` };
  }
  return { name, passed: true };
}

function assertNoCriticalTrivyFindings(name: string, path: string): GateResult {
  const report = JSON.parse(readFileSync(path, "utf8")) as {
    Results?: Array<{ Vulnerabilities?: Array<{ Severity?: string }> }>;
  };
  const findings =
    report.Results?.flatMap((result) => result.Vulnerabilities ?? []).filter(
      (finding) => ["CRITICAL"].includes(finding.Severity ?? ""),
    ) ?? [];
  if (findings.length > 0) {
    return {
      name,
      passed: false,
      reason: `${findings.length} critical findings`,
    };
  }
  return { name, passed: true };
}
