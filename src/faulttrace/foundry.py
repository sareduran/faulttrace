"""Small adapters around the Foundry Local SDK."""

from __future__ import annotations

from pathlib import Path

from foundry_local_sdk import Configuration, FoundryLocalManager


APP_NAME = "FaultTrace"
MODEL_CACHE_DIR = Path.home() / ".FaultTrace" / "cache" / "models"
EMBEDDING_MODEL = "qwen3-embedding-0.6b"
CHAT_MODEL = "qwen3.5-2b-text"


def _get_manager() -> FoundryLocalManager:
    """Initialize the process-wide Foundry manager exactly once."""

    if FoundryLocalManager.instance is None:
        FoundryLocalManager.initialize(
            Configuration(app_name=APP_NAME, model_cache_dir=str(MODEL_CACHE_DIR))
        )
    return FoundryLocalManager.instance


class FoundryEmbeddingService:
    """Load one local embedding model and expose a simple callable API."""

    def __init__(self, model_alias: str = EMBEDDING_MODEL) -> None:
        manager = _get_manager()
        self.model = manager.catalog.get_model(model_alias)
        self.model.load()
        self.client = self.model.get_embedding_client()

    def embed(self, text: str) -> list[float]:
        response = self.client.generate_embedding(text)
        return response.data[0].embedding

    def close(self) -> None:
        self.model.unload()

    def __enter__(self) -> "FoundryEmbeddingService":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class FoundryChatService:
    """Generate grounded incident summaries with the local chat model."""

    def __init__(self, model_alias: str = CHAT_MODEL, max_tokens: int = 700) -> None:
        manager = _get_manager()
        self.model = manager.catalog.get_model(model_alias)
        self.model.load()
        self.client = self.model.get_chat_client()
        self.client.settings.temperature = 0.1
        self.client.settings.max_tokens = max_tokens
        self.client.settings.random_seed = 42

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.complete_chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        return response.choices[0].message.content or ""

    def close(self) -> None:
        self.model.unload()

    def __enter__(self) -> "FoundryChatService":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
