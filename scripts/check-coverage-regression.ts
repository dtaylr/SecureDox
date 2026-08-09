import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";

const minCoverage = Number(process.env.GATE_MIN_COVERAGE ?? 80);
const coveragePath = "reports/coverage-unit.xml";
const coverage = existsSync(coveragePath) ? readCoveragePercent(coveragePath) : null;
const passed = coverage === null ? false : coverage >= minCoverage;

mkdirSync("reports", { recursive: true });
writeFileSync(
  "reports/coverage-summary.json",
  `${JSON.stringify(
    {
      coverage_percent: coverage,
      min_coverage_percent: minCoverage,
      status: passed ? "passed" : "missing_or_failed"
    },
    null,
    2
  )}\n`
);

if (!passed) {
  console.error(`coverage gate failed: ${coverage ?? "missing"} < ${minCoverage}`);
  process.exit(1);
}

function readCoveragePercent(path: string): number | null {
  const xml = readFileSync(path, "utf8");
  const match = xml.match(/line-rate="([0-9.]+)"/);
  return match ? Number(match[1]) * 100 : null;
}
