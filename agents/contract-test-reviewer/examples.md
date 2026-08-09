# Examples

## Response Shape Change

If `apps/api/app/schemas/document.py` changes, require:

- `tests/contract/document-api.consumer.test.ts`
- `tests/contract/document-api.provider.test.ts`
- API tests covering the changed field
- Frontend client type update if needed
