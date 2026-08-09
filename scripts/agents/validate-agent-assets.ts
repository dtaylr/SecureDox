import { emitJson } from "./lib/agent-utils.ts";
import { validateAgentAndSkillAssets } from "./lib/asset-validation.ts";

const result = validateAgentAndSkillAssets();
emitJson(result);

if (result.status !== "passed") {
  process.exitCode = 1;
}
