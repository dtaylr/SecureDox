import assert from "node:assert/strict";
import { validateAgentAndSkillAssets } from "../../scripts/agents/lib/asset-validation.ts";

const result = validateAgentAndSkillAssets();

assert.equal(result.status, "passed", JSON.stringify(result.issues, null, 2));
assert.ok(result.agents.some((agent) => agent.name === "test-architect"));
assert.ok(result.agents.some((agent) => agent.name === "security-reviewer"));
assert.ok(result.codex_agents.some((agent) => agent.name === "test-architect"));
assert.ok(result.codex_agents.some((agent) => agent.name === "security-reviewer"));
assert.ok(result.skills.some((skill) => skill.name === "agent-loop-kit"));
assert.ok(result.skills.some((skill) => skill.name === "anti-slop-patterns"));

console.log("Agent and skill asset validation passed.");
