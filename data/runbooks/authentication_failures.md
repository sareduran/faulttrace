# Authentication Failure Runbook

## Symptoms

Authentication incidents commonly produce HTTP 401 or 403 responses, invalid-token messages, expired credentials, or repeated login failures.

## Immediate response

Verify token expiration, signing-key rotation, clock synchronization, and identity-provider availability. Do not rotate credentials until the affected identity and scope are confirmed.

## Prevention

Alert on sudden increases in failed authentication, document key rotation procedures, and monitor identity-provider latency.

