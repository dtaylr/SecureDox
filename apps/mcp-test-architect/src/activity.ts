import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

const ACTIVITY_LOG = "reports/mcp-activity.log";

function sanitize(value: unknown): unknown {
  if (typeof value === "string") {
    return value.length > 240 ? `${value.slice(0, 240)}...[truncated]` : value;
  }
  if (Array.isArray(value)) {
    return value.slice(0, 20).map(sanitize);
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .filter(([key]) => !["test_code", "testCode", "code", "content"].includes(key))
        .map(([key, item]) => [key, sanitize(item)])
    );
  }
  return value;
}

export function logActivity(tool: string, args: Record<string, unknown>, status: "ok" | "error"): void {
  mkdirSync(dirname(ACTIVITY_LOG), { recursive: true });
  appendFileSync(
    ACTIVITY_LOG,
    `${JSON.stringify({
      ts: new Date().toISOString(),
      service_name: "securedox-mcp-test-architect",
      event_type: "mcp_tool_call",
      tool,
      status,
      args: sanitize(args)
    })}\n`
  );
}
