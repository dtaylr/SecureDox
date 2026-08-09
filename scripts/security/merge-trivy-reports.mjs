#!/usr/bin/env node
import { readFileSync, writeFileSync } from "node:fs";

const [targetPath, sourcePath, imageName] = process.argv.slice(2);
if (!targetPath || !sourcePath || !imageName) {
  console.error("Usage: merge-trivy-reports.mjs <target> <source> <image>");
  process.exit(2);
}

const target = JSON.parse(readFileSync(targetPath, "utf8"));
const source = JSON.parse(readFileSync(sourcePath, "utf8"));
target.Results ??= [];
for (const result of source.Results ?? []) {
  target.Results.push({ ...result, Target: `${imageName}:${result.Target ?? "image"}` });
}
writeFileSync(targetPath, `${JSON.stringify(target, null, 2)}\n`);
