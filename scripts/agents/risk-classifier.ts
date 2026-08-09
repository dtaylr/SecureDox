import { changedFilesFromArgs, classifyChanges, emitJson, parseArgs } from "./lib/agent-utils.ts";

const args = parseArgs();
const classification = classifyChanges(changedFilesFromArgs(args));

emitJson({
  risk: classification.risk,
  change_types: classification.change_types,
  reasons: classification.reasons,
  changed_files: classification.changed_files
});
