#!/usr/bin/env node
import { readFileSync, writeFileSync } from "node:fs";

const [targetPath, sourcePath, imageName] = process.argv.slice(2);
if (!targetPath || !sourcePath || !imageName) {
  console.error("Usage: merge-trivy-reports.mjs <target> <source> <image>");
  process.exit(2);
}

try {
  const target = readJsonReport(targetPath, "merged target");
  const source = readJsonReport(sourcePath, `Trivy report for ${imageName}`);
  target.Results ??= [];
  for (const result of source.Results ?? []) {
    target.Results.push({
      ...result,
      Target: `${imageName}:${result.Target ?? "image"}`,
    });
  }
  writeFileSync(targetPath, `${JSON.stringify(target, null, 2)}\n`);
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(message);
  process.exit(1);
}

function readJsonReport(path, label) {
  let raw;
  try {
    raw = readFileSync(path, "utf8").trim();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`${label} at ${path} could not be read: ${message}`);
  }
  if (!raw) {
    throw new Error(
      `${label} at ${path} is empty; check the preceding Trivy output.`,
    );
  }
  try {
    return JSON.parse(raw);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`${label} at ${path} is not valid JSON: ${message}`);
  }
}
