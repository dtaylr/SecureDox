import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

type PactInteraction = {
  description: string;
  response: {
    status: number;
    body: Record<string, unknown>;
  };
};

type PactContract = {
  consumer: { name: string };
  provider: { name: string };
  interactions: PactInteraction[];
};

function loadContract(): PactContract {
  const contractUrl = new URL("./contracts/document-api.pact.json", import.meta.url);
  return JSON.parse(readFileSync(contractUrl, "utf8")) as PactContract;
}

function interaction(contract: PactContract, description: string): PactInteraction {
  const found = contract.interactions.find((item) => item.description === description);
  assert.ok(found, `Missing Pact interaction: ${description}`);
  return found;
}

export async function runConsumerContractTests(): Promise<void> {
  const contract = loadContract();

  assert.equal(contract.consumer.name, "securedox-web");
  assert.equal(contract.provider.name, "securedox-api");

  const status = interaction(contract, "frontend expects document status shape").response.body;
  assert.equal(status.status, "REVIEW_REQUIRED");
  assert.equal(typeof status.id, "string");
  assert.equal(typeof status.needs_manual_review, "boolean");
  assert.ok(Array.isArray(status.extracted_fields));
  assert.ok(Array.isArray(status.validation_results));

  const ocr = interaction(contract, "frontend expects OCR confidence field").response.body;
  assert.equal(typeof ocr.field_name, "string");
  assert.equal(typeof ocr.confidence, "number");
  assert.ok(Number(ocr.confidence) >= 0 && Number(ocr.confidence) <= 1);
  assert.equal(typeof ocr.is_pii, "boolean");

  const validation = interaction(
    contract,
    "frontend expects validation error structure"
  ).response.body;
  const error = validation.error as Record<string, unknown>;
  assert.equal(error.code, "VALIDATION_ERROR");
  assert.equal(typeof error.correlation_id, "string");
  assert.ok(Array.isArray(error.details));

  const audit = interaction(contract, "frontend expects audit event shape").response.body;
  assert.equal(typeof audit.id, "string");
  assert.equal(typeof audit.action, "string");
  assert.equal(typeof audit.actor, "string");
  assert.equal(typeof audit.correlation_id, "string");
  assert.equal(typeof audit.detail, "object");
}

const invokedDirectly =
  process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href;

if (invokedDirectly) {
  await runConsumerContractTests();
}
