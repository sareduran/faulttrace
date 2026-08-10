# Database Connection Pool Runbook

## Symptoms

Connection pool exhaustion is usually visible as increasing active connection counts, acquisition timeouts, HTTP 503 responses, and failing health checks in services that depend on the database.

## Immediate response

1. Confirm that active connections reached the configured maximum.
2. Identify the first service that started producing connection timeout errors.
3. Check for leaked connections or transactions that remain open longer than expected.
4. Restart only the affected service if customer impact is continuing and a safe restart procedure exists.

## Prevention

Add alerts at 80% pool utilization, enforce connection timeouts, monitor long-running transactions, and verify that every code path closes its database connection.

