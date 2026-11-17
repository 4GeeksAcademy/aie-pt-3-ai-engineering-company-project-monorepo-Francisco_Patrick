"""Domain entities and value objects for the TrackFlow RAG & Knowledge Base domain.

Defines immutable domain representations for corporate knowledge documents,
semantic chunks, query requests, retrieved contexts, and grounded answers.
"""

import os
from pathlib import Path
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from dotenv import load_dotenv

PLACEHOLDER_API_KEYS = {
    "",
    "your_llm_api_key_here",
    "your_qdrant_api_key_here",
    "your_api_key_here",
    "changeme",
    "none",
    "null",
    "placeholder",
    "example_key",
}


def generate_chunk_id(source_document: str, chunk_index: int) -> uuid.UUID:
    """Generate a deterministic RFC 4122 UUID v5 for a knowledge chunk.

    Args:
        source_document: Canonical source document slug (e.g. "sla-delivery").
        chunk_index: Zero-based ordinal index of the chunk within the document.

    Returns:
        Deterministic UUID v5 instance.
    """
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"trackflow:{source_document}:{chunk_index}")


@dataclass(frozen=True)
class KnowledgeDocument:
    """Represents a canonical operational policy or service specification markdown file."""

    id: str
    title: str
    source_file: str
    language: str
    version: str
    raw_content: str
    sections: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class KnowledgeChunk:
    """An atomic, self-contained semantic segment of a KnowledgeDocument."""

    id: uuid.UUID
    company: str
    source_document: str
    section: str
    language: str
    chunk_index: int
    text: str
    vector: Optional[List[float]] = None

    def __post_init__(self) -> None:
        """Validate domain invariants for KnowledgeChunk."""
        if self.chunk_index < 0:
            raise ValueError("chunk_index must be a non-negative integer (>= 0).")
        if not self.text or len(self.text.strip()) < 20:
            raise ValueError("chunk text must not be empty and must contain at least 20 characters.")
        if self.company != "trackflow":
            raise ValueError("company must be 'trackflow'.")


@dataclass(frozen=True)
class QueryRequest:
    """User inquiry submitted from frontline interfaces or API consumers."""

    query: str
    language: str = "en"
    top_k: int = 3
    min_score: float = 0.62

    def __post_init__(self) -> None:
        """Validate domain invariants for QueryRequest."""
        stripped = self.query.strip() if self.query else ""
        if len(stripped) < 3 or len(stripped) > 1000:
            raise ValueError("query stripped length must be between 3 and 1000 characters.")
        if self.top_k < 1 or self.top_k > 10:
            raise ValueError("top_k must be between 1 and 10.")
        if self.min_score < 0.0 or self.min_score > 1.0:
            raise ValueError("min_score must be between 0.0 and 1.0.")


@dataclass(frozen=True)
class RetrievedContext:
    """Scored candidate chunk returned from semantic vector search."""

    chunk: KnowledgeChunk
    similarity_score: float
    rank: int


@dataclass(frozen=True)
class SourceCitation:
    """Verifiable source citation metadata included in a GroundedAnswer."""

    source_document: str
    section: str
    similarity_score: float


@dataclass(frozen=True)
class GroundedAnswer:
    """Final synthesized natural-language response delivered to the caller."""

    query: str
    answer: str
    is_refusal: bool
    sources: List[SourceCitation] = field(default_factory=list)
    execution_time_ms: float = 0.0


@dataclass(frozen=True)
class KnowledgeRuntimeConfig:
    """Externalized AI, LLM, Agent, Embedding, and Vector Store runtime configuration.

    Enforces secret masking (__repr__, __str__, to_sanitized_dict, sanitize_text)
    so LLM_API_KEY and QDRANT_API_KEY are never exposed in plaintext in logs,
    exceptions, or responses.
    """

    llm_api_key: Optional[str] = field(default=None, repr=False)
    llm_provider: str = "gemini"
    llm_model: str = "gemini-2.5-flash"
    agent_model: str = "gemini-2.5-pro"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    use_fastembed_onnx: bool = False
    similarity_threshold: float = 0.62
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = field(default=None, repr=False)
    qdrant_host: Optional[str] = None
    qdrant_port: int = 6333
    qdrant_collection_name: str = "trackflow_knowledge"

    def __post_init__(self) -> None:
        """Normalize fields and clamp similarity_threshold within [0.0, 1.0]."""
        provider = (self.llm_provider or "gemini").strip().lower() or "gemini"
        object.__setattr__(self, "llm_provider", provider)
        object.__setattr__(
            self, "llm_model", (self.llm_model or "gemini-2.5-flash").strip() or "gemini-2.5-flash"
        )
        object.__setattr__(
            self, "agent_model", (self.agent_model or "gemini-2.5-pro").strip() or "gemini-2.5-pro"
        )
        object.__setattr__(
            self,
            "embedding_model",
            (self.embedding_model or "BAAI/bge-small-en-v1.5").strip() or "BAAI/bge-small-en-v1.5",
        )
        clamped_threshold = max(0.0, min(1.0, float(self.similarity_threshold)))
        object.__setattr__(self, "similarity_threshold", round(clamped_threshold, 4))
        object.__setattr__(
            self,
            "qdrant_collection_name",
            (self.qdrant_collection_name or "trackflow_knowledge").strip() or "trackflow_knowledge",
        )
        if self.qdrant_api_key is not None:
            stripped_qdrant_key = self.qdrant_api_key.strip()
            if not stripped_qdrant_key or stripped_qdrant_key.lower() in PLACEHOLDER_API_KEYS:
                object.__setattr__(self, "qdrant_api_key", None)
            else:
                object.__setattr__(self, "qdrant_api_key", stripped_qdrant_key)

    @property
    def has_live_llm_key(self) -> bool:
        """Return True only when a non-placeholder LLM_API_KEY is configured and provider is live."""
        if self.llm_provider == "deterministic":
            return False
        if not self.llm_api_key:
            return False
        normalized = self.llm_api_key.strip().lower()
        return normalized not in PLACEHOLDER_API_KEYS

    @property
    def has_qdrant_api_key(self) -> bool:
        """Return True only when a non-placeholder QDRANT_API_KEY is configured."""
        if not self.qdrant_api_key:
            return False
        normalized = self.qdrant_api_key.strip().lower()
        return normalized not in PLACEHOLDER_API_KEYS

    def _masked_key_label(self) -> str:
        """Return the safe redacted label for llm_api_key."""
        return "***REDACTED***" if self.has_live_llm_key else "<unconfigured>"

    def _masked_qdrant_key_label(self) -> str:
        """Return the safe redacted label for qdrant_api_key."""
        return "***REDACTED***" if self.has_qdrant_api_key else "<unconfigured>"

    def sanitize_text(self, text: str) -> str:
        """Remove any accidental occurrence of raw API keys from a string."""
        if not text:
            return text
        cleaned = text
        for secret in (self.llm_api_key, self.qdrant_api_key):
            if secret and secret.strip():
                raw_key = secret.strip()
                if len(raw_key) >= 4 and raw_key in cleaned:
                    cleaned = cleaned.replace(raw_key, "***REDACTED***")
        return cleaned

    def to_sanitized_dict(self) -> Dict[str, Any]:
        """Return a dictionary representation with API keys strictly masked."""
        return {
            "llm_api_key": self._masked_key_label(),
            "has_live_llm_key": self.has_live_llm_key,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "agent_model": self.agent_model,
            "embedding_model": self.embedding_model,
            "use_fastembed_onnx": self.use_fastembed_onnx,
            "similarity_threshold": self.similarity_threshold,
            "qdrant_url": self.qdrant_url,
            "qdrant_api_key": self._masked_qdrant_key_label(),
            "has_qdrant_api_key": self.has_qdrant_api_key,
            "qdrant_host": self.qdrant_host,
            "qdrant_port": self.qdrant_port,
            "qdrant_collection_name": self.qdrant_collection_name,
        }

    def __repr__(self) -> str:
        """Return safe representation with llm_api_key and qdrant_api_key masked."""
        return (
            f"KnowledgeRuntimeConfig("
            f"llm_api_key='{self._masked_key_label()}', "
            f"llm_provider='{self.llm_provider}', "
            f"llm_model='{self.llm_model}', "
            f"agent_model='{self.agent_model}', "
            f"embedding_model='{self.embedding_model}', "
            f"use_fastembed_onnx={self.use_fastembed_onnx}, "
            f"similarity_threshold={self.similarity_threshold}, "
            f"qdrant_url={self.qdrant_url!r}, "
            f"qdrant_api_key='{self._masked_qdrant_key_label()}', "
            f"qdrant_host={self.qdrant_host!r}, "
            f"qdrant_port={self.qdrant_port}, "
            f"qdrant_collection_name='{self.qdrant_collection_name}')"
        )

    def __str__(self) -> str:
        """Return safe string representation with llm_api_key and qdrant_api_key masked."""
        return self.__repr__()

    @classmethod
    def from_env(
        cls,
        env: Optional[Mapping[str, str]] = None,
        load_dotenv_file: bool = True,
    ) -> "KnowledgeRuntimeConfig":
        """Load KnowledgeRuntimeConfig from environment variables or a mapping.

        Args:
            env: Optional mapping of environment variables (defaults to os.environ).
            load_dotenv_file: Whether to load services/api/.env into os.environ first.

        Returns:
            Validated KnowledgeRuntimeConfig instance.
        """
        if env is None and load_dotenv_file:
            env_path = Path(__file__).resolve().parent.parent.parent / ".env"
            if env_path.exists():
                load_dotenv(dotenv_path=env_path, override=False)

        source: Mapping[str, str] = env if env is not None else os.environ

        raw_key = source.get("LLM_API_KEY")
        cleaned_key = raw_key.strip() if raw_key and raw_key.strip() else None

        raw_qdrant_key = source.get("QDRANT_API_KEY")
        cleaned_qdrant_key: Optional[str] = None
        if raw_qdrant_key and raw_qdrant_key.strip():
            candidate = raw_qdrant_key.strip()
            if candidate.lower() not in PLACEHOLDER_API_KEYS:
                cleaned_qdrant_key = candidate

        raw_threshold = source.get("KNOWLEDGE_SIMILARITY_THRESHOLD", "0.62")
        try:
            parsed_threshold = float(raw_threshold)
        except (ValueError, TypeError):
            parsed_threshold = 0.62

        raw_port = source.get("QDRANT_PORT", "6333")
        try:
            parsed_port = int(raw_port)
        except (ValueError, TypeError):
            parsed_port = 6333

        raw_onnx = source.get("USE_FASTEMBED_ONNX", "false").strip().lower()
        use_onnx = raw_onnx in ("1", "true", "yes", "on")

        raw_url = source.get("QDRANT_URL", "").strip() or None
        raw_host = source.get("QDRANT_HOST", "").strip() or None

        return cls(
            llm_api_key=cleaned_key,
            llm_provider=source.get("LLM_PROVIDER", "gemini"),
            llm_model=source.get("LLM_MODEL", "gemini-2.5-flash"),
            agent_model=source.get("AGENT_MODEL", "gemini-2.5-pro"),
            embedding_model=source.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
            use_fastembed_onnx=use_onnx,
            similarity_threshold=parsed_threshold,
            qdrant_url=raw_url,
            qdrant_api_key=cleaned_qdrant_key,
            qdrant_host=raw_host,
            qdrant_port=parsed_port,
            qdrant_collection_name=source.get("QDRANT_COLLECTION_NAME", "trackflow_knowledge"),
        )

