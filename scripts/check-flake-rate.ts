import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";

const output = "reports/flake-summary.json";
mkdirSync("reports", { recursive: true });

const report = existsSync("tests/reports/playwright-results.json")
  ? JSON.parse(readFileSync("tests/reports/playwright-results.json", "utf8"))
  : null;

const retries = countRetries(report);
const total = report?.stats
  ? (report.stats.expected ?? 0) + (report.stats.unexpected ?? 0) + (report.stats.skipped ?? 0)
  : 0;
const flakeRate = total === 0 ? 0 : (retries / total) * 100;

writeFileSync(
  output,
  `${JSON.stringify({ flake_rate: `${flakeRate.toFixed(1)}%`, retries, total }, null, 2)}\n`
);
console.log(`flake_rate=${flakeRate.toFixed(1)}%`);

function countRetries(node: unknown): number {
  if (!node || typeof node !== "object") {
    return 0;
  }
  if (Array.isArray(node)) {
    return node.reduce((total, item) => total + countRetries(item), 0);
  }
  const object = node as Record<string, unknown>;
  const ownRetries = Array.isArray(object.results)
    ? object.results.filter((result) => {
        const value = result as { retry?: number };
        return (value.retry ?? 0) > 0;
      }).length
    : 0;
  return ownRetries + Object.values(object).reduce((total, value) => total + countRetries(value), 0);
}
