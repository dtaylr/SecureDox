import { changedFilesFromArgs, emitJson, parseArgs, selectImpactedTests } from "./lib/agent-utils.ts";

const args = parseArgs();
const files = changedFilesFromArgs(args);

emitJson(selectImpactedTests(files));
