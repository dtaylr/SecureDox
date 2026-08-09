import { changedFilesFromArgs, emitJson, parseArgs, securityImpact } from "./lib/agent-utils.ts";

const args = parseArgs();

emitJson(securityImpact(changedFilesFromArgs(args)));
