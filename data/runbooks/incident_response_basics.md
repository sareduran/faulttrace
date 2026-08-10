# Incident definition

A software incident is an unplanned event that degrades or interrupts the normal operation, availability, performance, security, or reliability of a software system. Examples include elevated error rates, unavailable services, severe latency, failed authentication, data-processing delays, and resource exhaustion. An alert is a signal that may require investigation; it becomes an incident when it has meaningful or imminent impact and requires a coordinated response.

# Incident severity

Severity describes business and technical impact, not how difficult an issue is to repair. A practical classification is:

- SEV-1 / Critical: widespread outage, critical business function unavailable, serious data-integrity or security risk, or no viable workaround.
- SEV-2 / High: major degradation or failure affecting many users or an important service, often with a limited workaround.
- SEV-3 / Medium: localized or partial degradation with limited user impact and a usable workaround.
- SEV-4 / Low: minor defect or operational concern with little immediate impact.

Severity should be reassessed as evidence changes. FaultTrace's impact score is a local prioritization aid derived from log severity, affected services, duration, and failure indicators; it is not a universal industry severity standard.

# Incident response lifecycle

The usual lifecycle is detection, triage, containment, mitigation, recovery, validation, and learning. First confirm the symptoms and affected services. Preserve timestamps and evidence, identify the incident owner, and communicate current impact. Prefer reversible mitigation such as reducing traffic, rolling back a recent change, isolating a failing dependency, or scaling a saturated component. After recovery, validate user-facing health and monitor for recurrence.

# Root cause and contributing factors

The triggering event, root cause, and contributing factors are different concepts. A trigger starts the visible failure. The probable root cause is the underlying condition that best explains the evidence. Contributing factors increase the likelihood or impact, such as missing alerts, unsafe retry behavior, inadequate capacity, or an incomplete rollout. When evidence is incomplete, describe the cause as probable and state what additional telemetry is required.

# Postmortem

A postmortem is a structured, blameless record created after an incident. It should contain an executive summary, impact, detection method, evidence-based timeline, probable root cause, contributing factors, response and recovery actions, what went well, what failed, and concrete follow-up actions with owners. Claims should be traceable to logs, metrics, changes, tickets, or runbooks. A postmortem is intended to improve the system and response process rather than assign personal blame.

# Evidence and safe answers

Incident analysis must distinguish observed facts from hypotheses. Logs prove only what they explicitly record. A runbook provides operational guidance but does not prove that its described failure caused the active incident. If the available logs and runbooks do not support an answer, request the missing metric, trace, configuration, deployment record, or domain-specific runbook instead of inventing an explanation.
