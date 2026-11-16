"""Unit tests for KnowledgeRuntimeConfig environment loading and secret masking (T025).

Verifies:
- Default configuration values when environment variables are unset
- Loading custom LLM_API_KEY, LLM_PROVIDER, LLM_MODEL, AGENT_MODEL, EMBEDDING_MODEL,
  USE_FASTEMBED_ONNX, KNOWLEDGE_SIMILARITY_THRESHOLD, and Qdrant parameters from env
- Placeholder detection for LLM_API_KEY (empty, 'your_llm_api_key_here', 'changeme', 'none', 'null')
- Threshold clamping within [0.0, 1.0] and graceful fallback to 0.62 on invalid strings
- Strict secret masking in __repr__, __str__, to_sanitized_dict, and sanitize_text.
"""

import os
from unittest.mock import patch

from domain.knowledge.entities import KnowledgeRuntimeConfig


class TestKnowledgeRuntimeConfig:
    """Unit test suite for KnowledgeRuntimeConfig value object (User Story 5)."""

    def test_defaults_when_env_is_empty(self) -> None:
        """Unset environment variables must resolve to documented TrackFlow defaults."""
        config = KnowledgeRuntimeConfig.from_env(env={}, load_dotenv_file=False)

        assert config.llm_api_key is None
        assert config.has_live_llm_key is False
        assert config.llm_provider == "gemini"
        assert config.llm_model == "gemini-2.5-flash"
        assert config.agent_model == "gemini-2.5-pro"
        assert config.embedding_model == "BAAI/bge-small-en-v1.5"
        assert config.use_fastembed_onnx is False
        assert config.similarity_threshold == 0.62
        assert config.qdrant_url is None
        assert config.qdrant_api_key is None
        assert config.has_qdrant_api_key is False
        assert config.qdrant_host is None
        assert config.qdrant_port == 6333
        assert config.qdrant_collection_name == "trackflow_knowledge"

    def test_custom_environment_variables_loaded_accurately(self) -> None:
        """All AI, LLM, Agent, Embedding, and Qdrant variables must load from environment."""
        custom_env = {
            "LLM_API_KEY": "sk-live-secret-trackflow-998877",
            "LLM_PROVIDER": "openai",
            "LLM_MODEL": "gpt-4o-mini",
            "AGENT_MODEL": "gpt-4o",
            "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2",
            "USE_FASTEMBED_ONNX": "true",
            "KNOWLEDGE_SIMILARITY_THRESHOLD": "0.71",
            "QDRANT_URL": "http://qdrant.internal:6333",
            "QDRANT_API_KEY": "qdrant-cloud-secret-jwt-token-12345",
            "QDRANT_HOST": "qdrant.internal",
            "QDRANT_PORT": "6334",
            "QDRANT_COLLECTION_NAME": "trackflow_knowledge_custom",
        }
        config = KnowledgeRuntimeConfig.from_env(env=custom_env, load_dotenv_file=False)

        assert config.has_live_llm_key is True
        assert config.llm_provider == "openai"
        assert config.llm_model == "gpt-4o-mini"
        assert config.agent_model == "gpt-4o"
        assert config.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
        assert config.use_fastembed_onnx is True
        assert config.similarity_threshold == 0.71
        assert config.qdrant_url == "http://qdrant.internal:6333"
        assert config.qdrant_api_key == "qdrant-cloud-secret-jwt-token-12345"
        assert config.has_qdrant_api_key is True
        assert config.qdrant_host == "qdrant.internal"
        assert config.qdrant_port == 6334
        assert config.qdrant_collection_name == "trackflow_knowledge_custom"

    def test_placeholder_api_keys_treated_as_unconfigured(self) -> None:
        """Placeholder values for LLM_API_KEY and QDRANT_API_KEY must be treated as unconfigured."""
        placeholders = [
            "",
            "   ",
            "your_llm_api_key_here",
            "YOUR_LLM_API_KEY_HERE",
            "your_qdrant_api_key_here",
            "your_api_key_here",
            "changeme",
            "none",
            "null",
        ]
        for placeholder in placeholders:
            config = KnowledgeRuntimeConfig.from_env(
                env={"LLM_API_KEY": placeholder, "QDRANT_API_KEY": placeholder},
                load_dotenv_file=False,
            )
            assert config.has_live_llm_key is False, f"Expected False for LLM placeholder '{placeholder}'"
            assert config.qdrant_api_key is None, f"Expected None for Qdrant placeholder '{placeholder}'"
            assert config.has_qdrant_api_key is False, f"Expected False for Qdrant placeholder '{placeholder}'"

    def test_deterministic_provider_disables_live_llm_key(self) -> None:
        """When LLM_PROVIDER is explicitly 'deterministic', has_live_llm_key must be False."""
        config = KnowledgeRuntimeConfig.from_env(
            env={
                "LLM_API_KEY": "sk-live-secret-trackflow-998877",
                "LLM_PROVIDER": "deterministic",
            },
            load_dotenv_file=False,
        )
        assert config.has_live_llm_key is False

    def test_similarity_threshold_clamping_and_invalid_fallback(self) -> None:
        """Similarity threshold must clamp to [0.0, 1.0] and fall back to 0.62 on non-numeric input."""
        high = KnowledgeRuntimeConfig.from_env(
            env={"KNOWLEDGE_SIMILARITY_THRESHOLD": "1.45"},
            load_dotenv_file=False,
        )
        assert high.similarity_threshold == 1.0

        low = KnowledgeRuntimeConfig.from_env(
            env={"KNOWLEDGE_SIMILARITY_THRESHOLD": "-0.35"},
            load_dotenv_file=False,
        )
        assert low.similarity_threshold == 0.0

        invalid = KnowledgeRuntimeConfig.from_env(
            env={"KNOWLEDGE_SIMILARITY_THRESHOLD": "not-a-float"},
            load_dotenv_file=False,
        )
        assert invalid.similarity_threshold == 0.62

    def test_secret_masking_in_repr_str_and_sanitized_dict(self) -> None:
        """Raw LLM_API_KEY and QDRANT_API_KEY must never appear in repr(), str(), or to_sanitized_dict()."""
        raw_secret = "AIzaSySecretKeyTrackFlowDoNotLeak12345"
        raw_qdrant_secret = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.qdrantSecret"
        config = KnowledgeRuntimeConfig.from_env(
            env={
                "LLM_API_KEY": raw_secret,
                "QDRANT_API_KEY": raw_qdrant_secret,
                "LLM_MODEL": "gemini-2.5-flash",
            },
            load_dotenv_file=False,
        )

        repr_str = repr(config)
        str_val = str(config)
        sanitized = config.to_sanitized_dict()

        assert raw_secret not in repr_str
        assert raw_secret not in str_val
        assert raw_secret not in str(sanitized)
        assert raw_qdrant_secret not in repr_str
        assert raw_qdrant_secret not in str_val
        assert raw_qdrant_secret not in str(sanitized)
        assert "***REDACTED***" in repr_str
        assert sanitized["llm_api_key"] == "***REDACTED***"
        assert sanitized["has_live_llm_key"] is True
        assert sanitized["qdrant_api_key"] == "***REDACTED***"
        assert sanitized["has_qdrant_api_key"] is True
        assert sanitized["llm_model"] == "gemini-2.5-flash"

    def test_unconfigured_secret_masking_shows_unconfigured_marker(self) -> None:
        """When LLM_API_KEY and QDRANT_API_KEY are unset or placeholder, sanitized representations show <unconfigured>."""
        config = KnowledgeRuntimeConfig.from_env(
            env={
                "LLM_API_KEY": "your_llm_api_key_here",
                "QDRANT_API_KEY": "your_qdrant_api_key_here",
            },
            load_dotenv_file=False,
        )

        assert "your_llm_api_key_here" not in repr(config)
        assert "your_qdrant_api_key_here" not in repr(config)
        assert "<unconfigured>" in repr(config)
        assert config.to_sanitized_dict()["llm_api_key"] == "<unconfigured>"
        assert config.to_sanitized_dict()["qdrant_api_key"] == "<unconfigured>"

    def test_sanitize_text_redacts_secret_occurrences(self) -> None:
        """sanitize_text must strip any accidental occurrence of raw API keys from log strings."""
        raw_secret = "sk-proj-super-secret-token-xyz987"
        raw_qdrant_secret = "qdrant-secret-bearer-token-998877"
        config = KnowledgeRuntimeConfig.from_env(
            env={"LLM_API_KEY": raw_secret, "QDRANT_API_KEY": raw_qdrant_secret},
            load_dotenv_file=False,
        )

        error_msg = (
            f"HTTP request failed for key={raw_secret} and qdrant={raw_qdrant_secret} with status 403"
        )
        cleaned = config.sanitize_text(error_msg)
        assert raw_secret not in cleaned
        assert raw_qdrant_secret not in cleaned
        assert "***REDACTED***" in cleaned

    def test_from_env_reads_os_environ_by_default(self) -> None:
        """from_env() with no explicit dict must read from os.environ."""
        with patch.dict(
            os.environ,
            {
                "LLM_API_KEY": "your_llm_api_key_here",
                "LLM_MODEL": "gemini-2.5-flash-custom",
                "AGENT_MODEL": "gemini-2.5-pro-custom",
            },
            clear=False,
        ):
            config = KnowledgeRuntimeConfig.from_env(load_dotenv_file=False)
            assert config.llm_model == "gemini-2.5-flash-custom"
            assert config.agent_model == "gemini-2.5-pro-custom"
            assert config.has_live_llm_key is False

    def test_grounded_generation_adapter_model_selection_and_sanitized_fallback(self) -> None:
        """GroundedGenerationAdapter selects LLM_MODEL vs AGENT_MODEL and falls back safely on error."""
        from domain.knowledge.entities import KnowledgeChunk, RetrievedContext, generate_chunk_id
        from infrastructure.adapters.grounded_generation_adapter import GroundedGenerationAdapter

        secret_key = "sk-live-secret-token-must-not-leak-999"
        config = KnowledgeRuntimeConfig.from_env(
            env={
                "LLM_API_KEY": secret_key,
                "LLM_PROVIDER": "openai",
                "LLM_MODEL": "gpt-4o-mini-custom",
                "AGENT_MODEL": "gpt-4o-agent-custom",
            },
            load_dotenv_file=False,
        )

        class FailingHttpClient:
            def post(self, *args: object, **kwargs: object) -> object:
                raise RuntimeError(f"Upstream error with token Bearer {secret_key}")

        adapter = GroundedGenerationAdapter(config=config, http_client=FailingHttpClient())
        assert adapter.select_active_model("What is the standard return window?") == "gpt-4o-mini-custom"
        assert (
            adapter.select_active_model("Can we offer a storage discount for 75 cubic meters?")
            == "gpt-4o-agent-custom"
        )

        chunk = KnowledgeChunk(
            id=generate_chunk_id("returns-policy", 1),
            company="trackflow",
            source_document="returns-policy",
            section="Standard Return Window & Costs",
            language="en",
            chunk_index=1,
            text="The standard return window is 30 days from delivery. Return shipping costs are covered by the client brand.",
        )
        ctx = RetrievedContext(chunk=chunk, similarity_score=0.88, rank=1)

        answer = adapter.generate_grounded_answer(
            query="What is TrackFlow's standard return window?",
            contexts=[ctx],
        )
        assert "30 days" in answer
        assert secret_key not in answer

