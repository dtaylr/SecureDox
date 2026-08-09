import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

export const REPO_ROOT = process.cwd();

export function gitChangedFiles(baseRef = "HEAD"): string[] {
  try {
    const output = execFileSync("git", ["diff", "--name-only", baseRef], {
      cwd: REPO_ROOT,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"]
    });
    return output
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .sort();
  } catch {
    return [];
  }
}

export function readRepoFile(path: string): string | null {
  const fullPath = join(REPO_ROOT, path);
  if (!existsSync(fullPath)) {
    return null;
  }
  return readFileSync(fullPath, "utf8");
}

export function unique<T>(values: T[]): T[] {
  return [...new Set(values)];
}

export function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string");
}

export function changedFilesFromArgs(args: Record<string, unknown>): string[] {
  const explicit = asStringArray(args.changed_files ?? args.changedFiles);
  return explicit.length > 0 ? explicit : gitChangedFiles(String(args.base_ref ?? args.baseRef ?? "HEAD"));
}
