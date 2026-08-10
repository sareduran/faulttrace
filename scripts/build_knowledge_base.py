"""Build FaultTrace's local SQLite vector index."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from faulttrace.foundry import FoundryEmbeddingService  # noqa: E402
from faulttrace.knowledge_base import KnowledgeBase  # noqa: E402


def main() -> None:
    knowledge_base = KnowledgeBase(PROJECT_ROOT / "data" / "faulttrace.db")
    with FoundryEmbeddingService() as embeddings:
        count = knowledge_base.index_directory(
            PROJECT_ROOT / "data" / "runbooks", embeddings.embed
        )
    print(f"Indexed {count} runbook chunks into {knowledge_base.database_path}")


if __name__ == "__main__":
    main()

