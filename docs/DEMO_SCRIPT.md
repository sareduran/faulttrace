# FaultTrace — five-minute presentation and demo script

## Slide 1 — Introduction

“FaultTrace is an offline, evidence-grounded incident analysis and postmortem assistant built with Microsoft Foundry Local. I did not train a model from scratch. I built a local RAG pipeline around Qwen embedding and chat models.”

## Slide 2 — Problem

“During an incident, facts are in logs while recovery knowledge is in separate runbooks. A generic assistant may mix those sources with unsupported assumptions. FaultTrace keeps observed facts, operational guidance, and uncertainty separate.”

## Slide 3 — Architecture

“First, logs are parsed, normalized, and sensitive values are masked. Runbooks are split into heading-aware chunks, embedded locally, and stored with their text in SQLite. A question is embedded and compared with cosine similarity. Accepted evidence and serious log lines are labelled before being sent to the local chat model. Finally, citation labels are audited.”

Mention the models:

- `qwen3-embedding-0.6b`
- `qwen3.5-2b-text`

## Slide 4 — Safety gate

“Retrieval runs before generation. If the best similarity is below 0.48, the language model never runs and FaultTrace says there is not enough local evidence. This screenshot shows the system rejecting a weakly supported question instead of inventing an answer.”

## Slide 5 — Verification

“The project has 33 passing automated tests and six passing retrieval-evaluation cases. The application reports retrieval time, generation time, and total end-to-end time separately. Deep generation is slow on my CPU-based laptop, which is a documented hardware limitation rather than a cloud dependency.”

## Live demo

1. Open `http://127.0.0.1:8501`.
2. Select **Database pool exhaustion**.
3. On **Overview**, show the Impact Score explanation and deterministic Failure Chain.
4. On **Analysis**, run **Quick analysis** and point to `[L#]` log and `[R#]` runbook citations.
5. On **Ask FaultTrace**, ask:

   `Why are requests returning HTTP 503, and what should we check first?`

6. Point to the retrieved source, similarity score, citation audit, and separate latency measurements.
7. If time permits, ask the rejection question:

   `What is the employee vacation policy?`

8. Explain that it is rejected because the evidence score is below the threshold.

## Closing

“FaultTrace is decision support, not autonomous remediation. Its value is simple: local RAG, verifiable evidence, and a safe fallback — evidence, not guesses.”

## Backup if deep generation is too slow

Use **Quick analysis** during the live demo and show a previously saved deep report under **Saved Reports**. Explain that the UI records actual generation latency and that model speed depends on local hardware.
