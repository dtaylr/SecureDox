import { ApiClient, type DocumentDetail, type DocumentStatus } from "../clients/ApiClient.js";
import { retryUntil, type RetryOptions } from "./retry.helper.js";

export async function waitForDocumentStatus(
  api: ApiClient,
  documentId: string,
  statuses: DocumentStatus[],
  options: RetryOptions = {}
): Promise<DocumentDetail> {
  return retryUntil(
    () => api.getDocument(documentId),
    (document) => statuses.includes(document.status),
    {
      description: `document ${documentId} to reach ${statuses.join(", ")}`,
      ...options
    }
  );
}

export async function waitForReviewReady(
  api: ApiClient,
  documentId: string,
  options: RetryOptions = {}
): Promise<DocumentDetail> {
  return waitForDocumentStatus(api, documentId, ["REVIEW_REQUIRED", "VALIDATED", "REJECTED"], options);
}
