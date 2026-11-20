"""Data pipelines package."""

from typing import Any

_RAG_EXPORTS = {"setup", "embed", "retrieve", "generate_answer", "query"}


def __getattr__(name: str) -> Any:
    """Lazy-load RAG pipeline functions from `data.pipelines.rag_pipeline`."""
    if name in _RAG_EXPORTS:
        from data.pipelines import rag_pipeline

        return getattr(rag_pipeline, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["embed", "generate_answer", "query", "retrieve", "setup"]

