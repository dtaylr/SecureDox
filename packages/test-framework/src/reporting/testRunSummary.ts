import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

export type TestRunSummary = {
  suite: string;
  startedAt: string;
  finishedAt: string;
  status: "passed" | "failed";
  evidence: Record<string, unknown>;
};

export function writeTestRunSummary(
  summary: TestRunSummary,
  outputPath = "tests/reports/test-run-summary.json"
): void {
  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, `${JSON.stringify(summary, null, 2)}\n`);
}
