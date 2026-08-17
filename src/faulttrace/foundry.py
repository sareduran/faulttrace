"""Small adapters around the Foundry Local SDK."""

from __future__ import annotations

from pathlib import Path

from foundry_local_sdk import Configuration, FoundryLocalManager


APP_NAME = "FaultTrace"
LEGACY_MODEL_CACHE_DIR = Path.home() / ".RootLens" / "cache" / "models"
DEFAULT_MODEL_CACHE_DIR = Path.home() / ".FaultTrace" / "cache" / "models"
# Reuse models downloaded before the project was renamed. New installations use
# the correctly branded directory instead of forcing existing users to download
# several gigabytes again.
MODEL_CACHE_DIR = (
    LEGACY_MODEL_CACHE_DIR
    if (LEGACY_MODEL_CACHE_DIR / "Microsoft").is_dir()
    else DEFAULT_MODEL_CACHE_DIR
)
EMBEDDING_MODEL = "qwen3-embedding-0.6b"
CHAT_MODEL = "qwen3.5-2b-text"


def _get_manager() -> FoundryLocalManager:
    """Initialize the process-wide Foundry manager exactly once."""

    if FoundryLocalManager.instance is None:
        FoundryLocalManager.initialize(
            Configuration(app_name=APP_NAME, model_cache_dir=str(MODEL_CACHE_DIR))
        )
    return FoundryLocalManager.instance


def _load_model(model_alias: str):
    """Download a missing model once, then load it from the local cache."""

    model = _get_manager().catalog.get_model(model_alias)
    if not model.is_cached:
        model.download()
    model.load()
    return model


class FoundryEmbeddingService:
    """Load one local embedding model and expose a simple callable API."""

    def __init__(self, model_alias: str = EMBEDDING_MODEL) -> None:
        self.model = _load_model(model_alias)
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
        self.model = _load_model(model_alias)
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
