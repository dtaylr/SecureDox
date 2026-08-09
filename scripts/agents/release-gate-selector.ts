import { changedFilesFromArgs, emitJson, parseArgs, releaseGatesForFiles } from "./lib/agent-utils.ts";

const args = parseArgs();
const files = changedFilesFromArgs(args);

emitJson({
  changed_files: files,
  ...releaseGatesForFiles(files)
});
