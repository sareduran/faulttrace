# High CPU Runbook

## Symptoms

High CPU incidents may include sustained processor utilization, slow request handling, thread-pool starvation, or health-check timeouts without a corresponding database error.

## Immediate response

Inspect the hottest process and threads, compare traffic with the normal baseline, capture a short performance profile, and check for infinite loops or unexpectedly expensive computations.

## Prevention

Define CPU saturation alerts, load-test critical endpoints, and monitor request latency together with processor utilization.

