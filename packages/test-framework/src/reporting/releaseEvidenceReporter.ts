import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

export type ReleaseEvidence = {
  phase: string;
  generatedAt: string;
  commitSha?: string;
  smokeTests: Array<{
    name: string;
    status: "passed" | "failed" | "skipped";
    evidence?: Record<string, unknown>;
  }>;
};

export function writeReleaseEvidence(
  evidence: ReleaseEvidence,
  outputPath = "tests/reports/release-evidence.json"
): void {
  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, `${JSON.stringify(evidence, null, 2)}\n`);
}
