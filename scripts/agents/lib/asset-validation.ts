import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

export type AssetValidationIssue = {
  path: string;
  message: string;
};

export type AgentAssetSummary = {
  name: string;
  files: string[];
};

export type SkillAssetSummary = {
  name: string;
  path: string;
};

export type CodexAgentSummary = {
  name: string;
  path: string;
};

export type AssetValidationResult = {
  status: "passed" | "failed";
  agents: AgentAssetSummary[];
  codex_agents: CodexAgentSummary[];
  skills: SkillAssetSummary[];
  issues: AssetValidationIssue[];
};

const REQUIRED_AGENT_FILES = ["prompt.md", "responsibilities.md", "examples.md"];
const ALLOWED_SKILL_FRONTMATTER_KEYS = new Set(["name", "description"]);
const DISALLOWED_SKILL_FILES = new Set([
  "AGENTS.md",
  "CLAUDE.md",
  "DECISIONS.md",
  "INSTALL.md",
  "PARKING_LOT.md",
  "README.md",
  "STATE.md"
]);

export function validateAgentAndSkillAssets(root = process.cwd()): AssetValidationResult {
  const issues: AssetValidationIssue[] = [];
  const agents = validateAgents(root, issues);
  const codexAgents = validateCodexAgents(root, agents, issues);
  const skills = validateSkills(root, issues);
  validateNoDsStore(root, issues);

  return {
    status: issues.length === 0 ? "passed" : "failed",
    agents,
    codex_agents: codexAgents,
    skills,
    issues
  };
}

function validateAgents(root: string, issues: AssetValidationIssue[]): AgentAssetSummary[] {
  const agentsDir = join(root, "agents");
  if (!existsSync(agentsDir)) {
    issues.push({ path: "agents", message: "agents directory is missing" });
    return [];
  }

  return readdirSync(agentsDir)
    .filter((entry) => isDirectory(join(agentsDir, entry)) && entry !== "subagents")
    .sort()
    .map((name) => {
      const dir = join(agentsDir, name);
      for (const requiredFile of REQUIRED_AGENT_FILES) {
        const filePath = join(dir, requiredFile);
        if (!existsSync(filePath)) {
          issues.push({ path: relative(root, filePath), message: "required agent file is missing" });
          continue;
        }
        if (readFileSync(filePath, "utf8").trim().length === 0) {
          issues.push({ path: relative(root, filePath), message: "required agent file is empty" });
        }
      }
      return {
        name,
        files: REQUIRED_AGENT_FILES.map((file) => relative(root, join(dir, file)))
      };
    });
}

function validateCodexAgents(
  root: string,
  agents: AgentAssetSummary[],
  issues: AssetValidationIssue[]
): CodexAgentSummary[] {
  const codexAgentsDir = join(root, ".codex", "agents");
  if (!existsSync(codexAgentsDir)) {
    issues.push({ path: ".codex/agents", message: "Codex custom agents directory is missing" });
    return [];
  }

  const codexAgents = readdirSync(codexAgentsDir)
    .filter((entry) => entry.endsWith(".toml"))
    .sort()
    .map((fileName) => {
      const filePath = join(codexAgentsDir, fileName);
      const source = readFileSync(filePath, "utf8");
      for (const field of ["name", "description", "developer_instructions"]) {
        if (!new RegExp(`^${field}\\s*=`, "m").test(source)) {
          issues.push({ path: relative(root, filePath), message: `Codex custom agent is missing ${field}` });
        }
      }
      const name = source.match(/^name\s*=\s*"([^"]+)"/m)?.[1] ?? fileName.replace(/\.toml$/, "");
      if (`${name}.toml` !== fileName) {
        issues.push({
          path: relative(root, filePath),
          message: `Codex custom agent file name should match agent name '${name}'`
        });
      }
      return { name, path: relative(root, filePath) };
    });

  const configuredAgentNames = new Set(codexAgents.map((agent) => agent.name));
  for (const agent of agents) {
    if (!configuredAgentNames.has(agent.name)) {
      issues.push({
        path: `.codex/agents/${agent.name}.toml`,
        message: "specialist agent is missing a Codex runtime config"
      });
    }
  }

  return codexAgents;
}

function validateSkills(root: string, issues: AssetValidationIssue[]): SkillAssetSummary[] {
  const skillsDir = join(root, "skills");
  if (!existsSync(skillsDir)) {
    issues.push({ path: "skills", message: "skills directory is missing" });
    return [];
  }

  return readdirSync(skillsDir)
    .filter((entry) => isDirectory(join(skillsDir, entry)))
    .sort()
    .map((name) => {
      const dir = join(skillsDir, name);
      const skillFile = join(dir, "SKILL.md");
      if (!existsSync(skillFile)) {
        issues.push({ path: relative(root, skillFile), message: "skill is missing SKILL.md" });
      } else {
        validateSkillFile(root, skillFile, name, issues);
      }
      validateNoCopiedSkillKitFiles(root, dir, issues);
      return { name, path: relative(root, skillFile) };
    });
}

function validateSkillFile(
  root: string,
  skillFile: string,
  directoryName: string,
  issues: AssetValidationIssue[]
): void {
  const source = readFileSync(skillFile, "utf8");
  if (!source.startsWith("---\n")) {
    issues.push({ path: relative(root, skillFile), message: "SKILL.md must start with YAML frontmatter" });
    return;
  }

  const closingIndex = source.indexOf("\n---", 4);
  if (closingIndex < 0) {
    issues.push({ path: relative(root, skillFile), message: "SKILL.md frontmatter is not closed" });
    return;
  }

  const frontmatter = source.slice(4, closingIndex).trim().split("\n");
  const keys = frontmatter
    .map((line) => line.match(/^([a-zA-Z0-9_-]+):/)?.[1])
    .filter((key): key is string => Boolean(key));

  for (const key of keys) {
    if (!ALLOWED_SKILL_FRONTMATTER_KEYS.has(key)) {
      issues.push({ path: relative(root, skillFile), message: `unsupported skill frontmatter key: ${key}` });
    }
  }

  if (!keys.includes("name")) {
    issues.push({ path: relative(root, skillFile), message: "skill frontmatter is missing name" });
  }
  if (!keys.includes("description")) {
    issues.push({ path: relative(root, skillFile), message: "skill frontmatter is missing description" });
  }

  const declaredName = frontmatter.find((line) => line.startsWith("name:"))?.replace(/^name:\s*/, "").trim();
  if (declaredName && declaredName !== directoryName) {
    issues.push({
      path: relative(root, skillFile),
      message: `skill name '${declaredName}' must match directory '${directoryName}'`
    });
  }
}

function validateNoCopiedSkillKitFiles(root: string, dir: string, issues: AssetValidationIssue[]): void {
  for (const entry of readdirSync(dir)) {
    const fullPath = join(dir, entry);
    if (DISALLOWED_SKILL_FILES.has(entry)) {
      issues.push({ path: relative(root, fullPath), message: "copied scaffold file does not belong in repo skills" });
    }
    if (entry === ".agent") {
      issues.push({ path: relative(root, fullPath), message: "copied agent-kit implementation directory is not needed" });
    }
  }
}

function validateNoDsStore(root: string, issues: AssetValidationIssue[]): void {
  for (const file of walk(join(root, "agents")).concat(walk(join(root, "skills")))) {
    if (file.endsWith(".DS_Store")) {
      issues.push({ path: relative(root, file), message: "macOS metadata file should not be committed" });
    }
  }
}

function walk(path: string): string[] {
  if (!existsSync(path)) {
    return [];
  }
  if (!isDirectory(path)) {
    return [path];
  }
  return readdirSync(path).flatMap((entry) => walk(join(path, entry)));
}

function isDirectory(path: string): boolean {
  return existsSync(path) && statSync(path).isDirectory();
}
