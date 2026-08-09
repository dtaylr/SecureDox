# IDOR Attempts Spike

Alert: `SecurityAccessDeniedSpike`

## Signals

- `security_access_denied_total{reason="forbidden"}` or tenant-scoped `NOT_FOUND` responses increase.
- Security dashboard shows repeated access denials.
- API logs include `event_type=http_request`, `user_id`, `tenant_id`, `correlation_id`, `status`, and `error_code`.

## Triage

1. Group denied requests by `user_id`, `tenant_id`, route, and source environment.
2. Confirm the API returned 404 for cross-tenant object access where enumeration would be dangerous.
3. Search audit logs for the affected `document_id`; cross-tenant reads should not create document audit events.
4. Compare with recent test runs to rule out expected security automation.

## Mitigation

- Disable or rotate the offending test token if abuse is confirmed.
- Preserve logs and correlation IDs for incident review.
- Do not reveal whether a document exists to the caller.

## Verification

- IDOR/security tests still pass.
- Denial rate returns to baseline.
- No unauthorized audit records or document changes exist.

## Failure Injection Drill

Run the authorization boundary test that uploads a document as `acme-lending` and attempts to read it as `northwind-health`. Confirm the response is `NOT_FOUND`, `security_access_denied_total` records the denial class where applicable, and logs retain the correlation ID.
