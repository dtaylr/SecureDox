import { apiContractDiff, changedFilesFromArgs, emitJson, parseArgs } from "./lib/agent-utils.ts";

const args = parseArgs();

emitJson(apiContractDiff(changedFilesFromArgs(args)));
