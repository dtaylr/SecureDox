import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { runConsumerContractTests } from "./document-api.consumer.test.js";
import { runProviderContractTests } from "./document-api.provider.test.js";

type ContractCase = {
  name: string;
  run: () => Promise<void>;
};

type ContractResult = {
  name: string;
  durationMs: number;
  error?: Error;
};

const cases: ContractCase[] = [
  {
    name: "document-api consumer contract",
    run: runConsumerContractTests
  },
  {
    name: "document-api provider contract",
    run: runProviderContractTests
  }
];

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

function asError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}

function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function writeJunit(results: ContractResult[]): void {
  const failures = results.filter((result) => result.error);
  const casesXml = results
    .map((result) => {
      const seconds = (result.durationMs / 1000).toFixed(3);
      const failure = result.error
        ? `<failure message="${escapeXml(result.error.message)}">${escapeXml(
            result.error.stack ?? result.error.message
          )}</failure>`
        : "";
      return `<testcase classname="securedox.contract" name="${escapeXml(
        result.name
      )}" time="${seconds}">${failure}</testcase>`;
    })
    .join("");

  const reportPath = resolve(repoRoot, "reports/junit-contract.xml");
  mkdirSync(dirname(reportPath), { recursive: true });
  writeFileSync(
    reportPath,
    `<testsuite name="securedox-contract" tests="${results.length}" failures="${failures.length}">${casesXml}</testsuite>\n`
  );
}

const results: ContractResult[] = [];
for (const testCase of cases) {
  const started = Date.now();
  try {
    await testCase.run();
    results.push({ name: testCase.name, durationMs: Date.now() - started });
  } catch (error) {
    results.push({
      name: testCase.name,
      durationMs: Date.now() - started,
      error: asError(error)
    });
  }
}

writeJunit(results);

const failures = results.filter((result) => result.error);
if (failures.length > 0) {
  for (const failure of failures) {
    console.error(`${failure.name}: ${failure.error?.message}`);
  }
  process.exitCode = 1;
} else {
  console.log(`Contract verification passed (${results.length} checks).`);
}
