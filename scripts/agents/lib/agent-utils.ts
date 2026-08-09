import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

export type ChangeType =
  | "frontend_ui_change"
  | "api_contract_change"
  | "database_schema_change"
  | "auth_security_sensitive_change"
  | "worker_queue_change"
  | "ocr_logic_change"
  | "infra_change"
  | "dockerfile_change"
  | "dependency_change"
  | "observability_change"
  | "test_only_change"
  | "docs_only_change";

export type Risk = "low" | "medium" | "high" | "critical";

export type Classification = {
  changed_files: string[];
  change_types: ChangeType[];
  risk: Risk;
  reasons: string[];
};

export type ImpactedTestSelection = {
  change_type: ChangeType | "mixed_change" | "no_change";
  risk: Risk;
  required_checks: string[];
  recommended_reviewers: string[];
  changed_files: string[];
  reasons: string[];
};

const CHECKS_BY_TYPE: Record<ChangeType, string[]> = {
  frontend_ui_change: ["e2e-critical", "accessibility-smoke"],
  api_contract_change: ["api-tests", "contract-tests", "e2e-critical", "release-readiness"],
  database_schema_change: ["db-tests", "api-tests", "release-readiness"],
  auth_security_sensitive_change: ["security-authz-tests", "api-negative-tests", "security-gates", "release-readiness"],
  worker_queue_change: ["api-tests", "db-tests", "ocr-tests", "observability-tests"],
  ocr_logic_change: ["ocr-validation-tests", "db-tests", "release-readiness"],
  infra_change: ["security-gates", "observability-tests", "release-readiness"],
  dockerfile_change: ["dockerfile-lint", "container-scan", "security-gates"],
  dependency_change: ["dependency-scan", "sbom", "security-gates", "release-readiness"],
  observability_change: ["observability-tests", "sre-runbook-review"],
  test_only_change: ["changed-test-suite", "flake-check"],
  docs_only_change: ["documentation-review"]
};

const REVIEWERS_BY_TYPE: Record<ChangeType, string[]> = {
  frontend_ui_change: ["test-architect"],
  api_contract_change: ["contract-test-reviewer", "test-architect"],
  database_schema_change: ["test-architect", "release-gate-analyst"],
  auth_security_sensitive_change: ["security-reviewer", "test-architect"],
  worker_queue_change: ["test-architect", "observability-reviewer"],
  ocr_logic_change: ["test-architect", "release-gate-analyst"],
  infra_change: ["security-reviewer", "observability-reviewer"],
  dockerfile_change: ["security-reviewer"],
  dependency_change: ["security-reviewer", "release-gate-analyst"],
  observability_change: ["observability-reviewer", "documentation-maintainer"],
  test_only_change: ["flaky-test-triage", "test-architect"],
  docs_only_change: ["documentation-maintainer"]
};

const RISK_BY_TYPE: Record<ChangeType, Risk> = {
  frontend_ui_change: "medium",
  api_contract_change: "high",
  database_schema_change: "high",
  auth_security_sensitive_change: "critical",
  worker_queue_change: "high",
  ocr_logic_change: "high",
  infra_change: "high",
  dockerfile_change: "high",
  dependency_change: "critical",
  observability_change: "medium",
  test_only_change: "medium",
  docs_only_change: "low"
};

export function repoRoot(): string {
  return process.cwd();
}

export function parseArgs(argv = process.argv.slice(2)): Record<string, string | string[] | boolean> {
  const args: Record<string, string | string[] | boolean> = {};
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index] ?? "";
    if (!item.startsWith("--")) {
      continue;
    }
    const key = item.slice(2);
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) {
      args[key] = true;
      continue;
    }
    if (args[key]) {
      const existing = args[key];
      args[key] = Array.isArray(existing) ? [...existing, next] : [String(existing), next];
    } else {
      args[key] = next;
    }
    index += 1;
  }
  return args;
}

export function changedFilesFromArgs(args: Record<string, string | string[] | boolean>): string[] {
  const raw = args.file ?? args.files ?? args.changed_file ?? args.changed_files;
  if (Array.isArray(raw)) {
    return raw.flatMap(splitFileList).sort();
  }
  if (typeof raw === "string") {
    return splitFileList(raw).sort();
  }
  return gitChangedFiles(String(args.base ?? args.base_ref ?? "HEAD"));
}

export function gitChangedFiles(baseRef = "HEAD"): string[] {
  try {
    const output = execFileSync("git", ["diff", "--name-only", baseRef], {
      cwd: repoRoot(),
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"]
    });
    return splitFileList(output).sort();
  } catch {
    return [];
  }
}

export function classifyChanges(files: string[]): Classification {
  const changeTypes = unique(files.flatMap(classifyFile));
  const reasons = changeTypes.map((type) => reasonForType(type));
  return {
    changed_files: files,
    change_types: changeTypes,
    risk: maxRisk(changeTypes),
    reasons
  };
}

export function selectImpactedTests(files: string[]): ImpactedTestSelection {
  const classification = classifyChanges(files);
  const checks = unique(classification.change_types.flatMap((type) => CHECKS_BY_TYPE[type]));
  const reviewers = unique(classification.change_types.flatMap((type) => REVIEWERS_BY_TYPE[type]));
  return {
    change_type:
      classification.change_types.length === 0
        ? "no_change"
        : classification.change_types.length === 1
          ? classification.change_types[0] ?? "no_change"
          : "mixed_change",
    risk: classification.risk,
    required_checks: checks,
    recommended_reviewers: reviewers,
    changed_files: files,
    reasons: classification.reasons
  };
}

export function releaseGatesForFiles(files: string[]): {
  risk: Risk;
  required_gates: string[];
  warning_gates: string[];
  recommended_reviewers: string[];
} {
  const impacted = selectImpactedTests(files);
  const gates = new Set(["release-readiness"]);
  const warnings = new Set<string>();
  for (const check of impacted.required_checks) {
    if (/security|container|dependency|sbom|contract|db|api|ocr|e2e|release/.test(check)) {
      gates.add(check);
    } else {
      warnings.add(check);
    }
  }
  return {
    risk: impacted.risk,
    required_gates: [...gates].sort(),
    warning_gates: [...warnings].sort(),
    recommended_reviewers: impacted.recommended_reviewers
  };
}

export function routeMap(files = ["apps/api/app/api/v1"]): Array<{
  file: string;
  method: string;
  route: string;
}> {
  return files.flatMap((file) => {
    const fullPath = join(repoRoot(), file);
    if (!existsSync(fullPath)) {
      return [];
    }
    const candidates = statSync(fullPath).isDirectory()
      ? walk(fullPath).filter((path) => path.endsWith(".py"))
      : [fullPath];
    return candidates.flatMap((candidate) => {
      const source = readFileSync(candidate, "utf8");
      const matches = [...source.matchAll(/@router\.(get|post|patch|put|delete)\(\s*["']([^"']*)/g)];
      return matches.map((match) => ({
        file: relative(repoRoot(), candidate),
        method: (match[1] ?? "get").toUpperCase(),
        route: match[2] ?? ""
      }));
    });
  });
}

export function apiContractDiff(files: string[]): Record<string, unknown> {
  const changed = files.filter((file) =>
    /apps\/api\/app\/schemas|apps\/api\/app\/api\/v1|packages\/contracts|tests\/contract|openapi/.test(file)
  );
  return {
    change_type: "api_contract_change",
    risk: changed.length > 0 ? "high" : "low",
    changed_files: changed,
    required_checks: changed.length > 0 ? CHECKS_BY_TYPE.api_contract_change : []
  };
}

export function dbSchemaDiff(files: string[]): Record<string, unknown> {
  const changed = files.filter((file) => /alembic\/versions|apps\/api\/app\/models|db\/|securedox_shared\/enums/.test(file));
  return {
    change_type: "database_schema_change",
    risk: changed.length > 0 ? "high" : "low",
    changed_files: changed,
    required_checks: changed.length > 0 ? CHECKS_BY_TYPE.database_schema_change : []
  };
}

export function securityImpact(files: string[]): Record<string, unknown> {
  const changed = files.filter((file) => classifyFile(file).includes("auth_security_sensitive_change"));
  return {
    change_type: "auth_security_sensitive_change",
    risk: changed.length > 0 ? "critical" : "low",
    changed_files: changed,
    required_checks: changed.length > 0 ? CHECKS_BY_TYPE.auth_security_sensitive_change : []
  };
}

export function observabilityImpact(files: string[]): Record<string, unknown> {
  const changed = files.filter((file) => classifyFile(file).includes("observability_change"));
  return {
    change_type: "observability_change",
    risk: changed.length > 0 ? "medium" : "low",
    changed_files: changed,
    required_checks: changed.length > 0 ? CHECKS_BY_TYPE.observability_change : []
  };
}

export function emitJson(value: unknown): void {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

function classifyFile(file: string): ChangeType[] {
  const types: ChangeType[] = [];
  if (/^apps\/web\//.test(file)) types.push("frontend_ui_change");
  if (/apps\/api\/app\/schemas|apps\/api\/app\/api\/v1|packages\/contracts|tests\/contract|openapi/.test(file)) {
    types.push("api_contract_change");
  }
  if (/alembic\/versions|apps\/api\/app\/models|db\/|securedox_shared\/enums/.test(file)) {
    types.push("database_schema_change");
  }
  if (/auth|security|gitleaks|semgrep|trivy|idor|secret|jwt|permission|authorization/.test(file)) {
    types.push("auth_security_sensitive_change");
  }
  if (/apps\/worker|services\/queue|messages\.py|IntakeJob/.test(file)) types.push("worker_queue_change");
  if (/ocr|test-documents|extraction|rules/.test(file)) types.push("ocr_logic_change");
  if (/infra\/|nginx|\.github\/workflows|docker-compose|prometheus|grafana/.test(file)) types.push("infra_change");
  if (/Dockerfile|dockerfile/.test(file)) types.push("dockerfile_change");
  if (/package\.json|yarn\.lock|requirements|pyproject|poetry\.lock|package-lock/.test(file)) {
    types.push("dependency_change");
  }
  if (/observability|metrics|logging|sre-runbooks|prometheus|grafana|alerts/.test(file)) {
    types.push("observability_change");
  }
  if (/^tests\//.test(file) || /\.spec\.ts$|test_.*\.py$/.test(file)) types.push("test_only_change");
  if (/^docs\//.test(file) || /\.md$/.test(file)) types.push("docs_only_change");
  return unique(types);
}

function splitFileList(raw: string): string[] {
  return raw
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function maxRisk(types: ChangeType[]): Risk {
  if (types.length === 0) return "low";
  const order: Risk[] = ["low", "medium", "high", "critical"];
  return types.reduce<Risk>((current, type) => {
    return order.indexOf(RISK_BY_TYPE[type]) > order.indexOf(current) ? RISK_BY_TYPE[type] : current;
  }, "low");
}

function reasonForType(type: ChangeType): string {
  return `${type} requires ${CHECKS_BY_TYPE[type].join(", ")}`;
}

function unique<T>(values: T[]): T[] {
  return [...new Set(values)];
}

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const fullPath = join(dir, entry);
    return statSync(fullPath).isDirectory() ? walk(fullPath) : [fullPath];
  });
}
