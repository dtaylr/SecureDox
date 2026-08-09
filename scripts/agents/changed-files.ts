import { changedFilesFromArgs, classifyChanges, emitJson, parseArgs } from "./lib/agent-utils.ts";

const args = parseArgs();
const files = changedFilesFromArgs(args);

emitJson(classifyChanges(files));
