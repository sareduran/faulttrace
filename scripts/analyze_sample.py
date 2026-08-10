"""Run a complete local RAG analysis of the bundled sample incident."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from faulttrace import parse_log_file  # noqa: E402
from faulttrace.analysis import SYSTEM_PROMPT, build_analysis_prompt, build_incident_query  # noqa: E402
from faulttrace.foundry import FoundryChatService, FoundryEmbeddingService  # noqa: E402
from faulttrace.knowledge_base import KnowledgeBase  # noqa: E402


def main() -> None:
    events, rejected = parse_log_file(PROJECT_ROOT / "data" / "sample_incident.log")
    if rejected:
        raise RuntimeError(f"Sample contains {len(rejected)} rejected log lines")

    knowledge_base = KnowledgeBase(PROJECT_ROOT / "data" / "faulttrace.db")
    with FoundryEmbeddingService() as embeddings:
        runbooks = knowledge_base.search(
            build_incident_query(events), embeddings.embed, limit=3
        )

    prompt = build_analysis_prompt(events, runbooks)
    with FoundryChatService() as chat:
        answer = chat.complete(SYSTEM_PROMPT, prompt)
    print(answer)


if __name__ == "__main__":
    main()

