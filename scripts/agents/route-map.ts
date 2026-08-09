import { emitJson, parseArgs, routeMap } from "./lib/agent-utils.ts";

const args = parseArgs();
const raw = args.path ?? args.paths;
const paths = Array.isArray(raw) ? raw.map(String) : typeof raw === "string" ? raw.split(",") : undefined;

emitJson({
  routes: routeMap(paths)
});
