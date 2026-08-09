import { changedFilesFromArgs, dbSchemaDiff, emitJson, parseArgs } from "./lib/agent-utils.ts";

const args = parseArgs();

emitJson(dbSchemaDiff(changedFilesFromArgs(args)));
