import { changedFilesFromArgs, emitJson, observabilityImpact, parseArgs } from "./lib/agent-utils.ts";

const args = parseArgs();

emitJson(observabilityImpact(changedFilesFromArgs(args)));
