#!/usr/bin/env node
import { callTool, tools } from "./tools.ts";

type JsonRpcRequest = {
  jsonrpc?: "2.0";
  id?: string | number | null;
  method?: string;
  params?: Record<string, unknown>;
};

function toolListPayload() {
  return {
    tools: tools.map((tool) => ({
      name: tool.name,
      description: tool.description,
      inputSchema: tool.inputSchema
    }))
  };
}

function respond(id: JsonRpcRequest["id"], result: unknown): void {
  writeMessage({ jsonrpc: "2.0", id: id ?? null, result });
}

function respondError(id: JsonRpcRequest["id"], code: number, message: string): void {
  writeMessage({ jsonrpc: "2.0", id: id ?? null, error: { code, message } });
}

function writeMessage(payload: unknown): void {
  const body = JSON.stringify(payload);
  process.stdout.write(`Content-Length: ${Buffer.byteLength(body, "utf8")}\r\n\r\n${body}`);
}

function toTextContent(value: unknown) {
  return [
    {
      type: "text",
      text: JSON.stringify(value, null, 2)
    }
  ];
}

function handle(request: JsonRpcRequest): void {
  try {
    switch (request.method) {
      case "initialize":
        respond(request.id, {
          protocolVersion: "2024-11-05",
          capabilities: {
            tools: {}
          },
          serverInfo: {
            name: "securedox-mcp-test-architect",
            version: "0.1.0"
          }
        });
        return;
      case "tools/list":
        respond(request.id, toolListPayload());
        return;
      case "tools/call": {
        const params = request.params ?? {};
        const name = typeof params.name === "string" ? params.name : "";
        const args =
          params.arguments && typeof params.arguments === "object"
            ? (params.arguments as Record<string, unknown>)
            : {};
        const result = callTool(name, args);
        respond(request.id, { content: toTextContent(result), isError: false });
        return;
      }
      case "notifications/initialized":
        return;
      default:
        respondError(request.id, -32601, `Unsupported MCP method: ${request.method ?? "<missing>"}`);
    }
  } catch (error) {
    respondError(request.id, -32000, error instanceof Error ? error.message : String(error));
  }
}

function parseFrames(buffer: Buffer): { messages: JsonRpcRequest[]; rest: Buffer } {
  const messages: JsonRpcRequest[] = [];
  let cursor = buffer;
  while (cursor.length > 0) {
    const headerEnd = cursor.indexOf("\r\n\r\n");
    if (headerEnd < 0) {
      break;
    }
    const header = cursor.subarray(0, headerEnd).toString("utf8");
    const lengthMatch = header.match(/Content-Length:\s*(\d+)/i);
    if (!lengthMatch) {
      throw new Error("Missing Content-Length header.");
    }
    const length = Number(lengthMatch[1] ?? "0");
    const bodyStart = headerEnd + 4;
    const bodyEnd = bodyStart + length;
    if (cursor.length < bodyEnd) {
      break;
    }
    messages.push(JSON.parse(cursor.subarray(bodyStart, bodyEnd).toString("utf8")) as JsonRpcRequest);
    cursor = cursor.subarray(bodyEnd);
  }
  return { messages, rest: cursor };
}

if (process.argv.includes("--list-tools")) {
  console.log(JSON.stringify(toolListPayload(), null, 2));
  process.exit(0);
}

let pending = Buffer.alloc(0);
process.stdin.on("data", (chunk: Buffer) => {
  pending = Buffer.concat([pending, chunk]);
  try {
    const parsed = parseFrames(pending);
    pending = parsed.rest;
    for (const message of parsed.messages) {
      handle(message);
    }
  } catch (error) {
    respondError(null, -32700, error instanceof Error ? error.message : String(error));
    pending = Buffer.alloc(0);
  }
});

process.stdin.resume();
