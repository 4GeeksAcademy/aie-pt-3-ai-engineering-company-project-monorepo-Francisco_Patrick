"""FastAPI dependency injection providers.

Centralizes dependency resolution across presentation endpoints, providing access
to database connections, driven adapters, repository ports, and application services.
"""

from typing import TYPE_CHECKING, Any, Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session
from tinydb import TinyDB

from domain.models import User
from domain.exceptions import AuthenticationError
from domain.ports import (
    ProfileRepositoryPort,
    SecurityPort,
    UserRepositoryPort,
)
from domain.common.ports import CachePort
from domain.inventory.ports import InventoryRepositoryPort
from domain.suppliers.ports import SupplierRepositoryPort
from application.services.auth_service import AuthService
from application.services.incident_service import IncidentService
from application.services.profile_service import ProfileService
from application.services.user_service import UserService
from application.suppliers.supplier_service import SupplierService
from application.inventory.inventory_service import InventoryService
from application.telemetry.telemetry_service import TelemetryService
from application.telemetry.cache import TelemetryReportCache
from application.telemetry.report_service import TelemetryReportService
from application.incidents.csv_report_service import IncidentCsvReportService
from application.services.knowledge_service import KnowledgeService
from application.services.support_agent_service import SupportAgentService
from application.services.trace_registry import TraceRegistry
from domain.agent.ports import (
    AgentMemoryRepositoryPort,
    InventoryStockToolPort,
    MemoryAuditLogRepositoryPort,
    MemoryGuardrailPort,
    SupportAgentServicePort,
    SupportTicketToolPort,
    TraceRegistryPort,
    UserIntentClassifierPort,
)
from domain.telemetry.ports import TelemetryRepositoryPort
from domain.knowledge.entities import KnowledgeRuntimeConfig
from domain.knowledge.ports import (
    EmbeddingServicePort,
    LLMGenerationPort,
    VectorStorePort,
)

if TYPE_CHECKING:
    from application.services.email_service import EmailService
    from infrastructure.adapters.tiny_db_repository import (
        TinyDBAuditLogRepository,
        TinyDBPasswordResetTokenRepository,
    )
    from infrastructure.middleware.rate_limiter import RateLimiter


# --- OAuth2 Scheme ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


# --- Persistence Dependencies ---
def get_tinydb_dep() -> TinyDB:
    """Dependency provider for TinyDB document store client."""
    from infrastructure.persistence.tinydb.client import get_tinydb
    return get_tinydb()


def get_sqlmodel_session_dep() -> Generator[Session, None, None]:
    """Dependency provider for SQLModel relational database session."""
    from infrastructure.persistence.sqlmodel.client import get_db
    yield from get_db()


# --- Infrastructure Adapter Dependencies ---
def get_security_adapter_dep() -> SecurityPort:
    """Dependency provider for cryptographic and JWT token security port."""
    from infrastructure.adapters.security_adapter import JwtSecurityAdapter
    return JwtSecurityAdapter()


def get_cache_dep() -> CachePort:
    """Dependency provider for in-memory CachePort adapter."""
    from infrastructure.cache.memory_cache_adapter import memory_cache_adapter
    return memory_cache_adapter


# --- Repository Port Dependencies ---
def get_user_repository_dep(
    db: TinyDB = Depends(get_tinydb_dep),
) -> UserRepositoryPort:
    """Dependency provider for TinyDBUserRepository."""
    from infrastructure.adapters.tiny_db_repository import TinyDBUserRepository
    return TinyDBUserRepository(db)


def get_profile_repository_dep(
    db: TinyDB = Depends(get_tinydb_dep),
) -> ProfileRepositoryPort:
    """Dependency provider for TinyDBProfileRepository."""
    from infrastructure.adapters.tiny_db_repository import TinyDBProfileRepository
    return TinyDBProfileRepository(db)


def get_incident_repository_dep(
    db: TinyDB = Depends(get_tinydb_dep),
) -> Any:
    """Dependency provider for TinyDBIncidentRepository."""
    from infrastructure.adapters.tiny_db_incident_repository import TinyDBIncidentRepository
    return TinyDBIncidentRepository(db)


# --- Application Service Dependencies ---
def get_user_service_dep(
    user_repo: UserRepositoryPort = Depends(get_user_repository_dep),
    profile_repo: ProfileRepositoryPort = Depends(get_profile_repository_dep),
    security_port: SecurityPort = Depends(get_security_adapter_dep),
) -> UserService:
    """Dependency provider for UserService."""
    return UserService(
        user_repo=user_repo,
        profile_repo=profile_repo,
        security_port=security_port,
    )


def get_auth_service_dep(
    user_repo: UserRepositoryPort = Depends(get_user_repository_dep),
    security_port: SecurityPort = Depends(get_security_adapter_dep),
) -> AuthService:
    """Dependency provider for AuthService."""
    return AuthService(
        user_repo=user_repo,
        security_port=security_port,
    )


def get_profile_service_dep(
    profile_repo: ProfileRepositoryPort = Depends(get_profile_repository_dep),
) -> ProfileService:
    """Dependency provider for ProfileService."""
    return ProfileService(profile_repo=profile_repo)


def get_incident_service_dep(
    incident_repo: Any = Depends(get_incident_repository_dep),
) -> IncidentService:
    """Dependency provider for IncidentService."""
    return IncidentService(repo=incident_repo)


def get_supplier_repository_dep(
    db: TinyDB = Depends(get_tinydb_dep),
) -> SupplierRepositoryPort:
    """Dependency provider for TinyDBSupplierRepository."""
    from infrastructure.persistence.tinydb.supplier_repository import TinyDBSupplierRepository
    return TinyDBSupplierRepository(db)


def get_supplier_service_dep(
    supplier_repo: SupplierRepositoryPort = Depends(get_supplier_repository_dep),
    cache: CachePort = Depends(get_cache_dep),
) -> SupplierService:
    """Dependency provider for SupplierService."""
    return SupplierService(supplier_repo=supplier_repo, cache=cache)


def get_inventory_repository_dep(
    session: Session = Depends(get_sqlmodel_session_dep),
) -> InventoryRepositoryPort:
    """Dependency provider for SQLModelInventoryRepository bound to the request session."""
    from infrastructure.persistence.sqlmodel.inventory_repository import SQLModelInventoryRepository
    return SQLModelInventoryRepository(session)


def get_inventory_service_dep(
    inventory_repo: InventoryRepositoryPort = Depends(get_inventory_repository_dep),
    cache: CachePort = Depends(get_cache_dep),
) -> InventoryService:
    """Dependency provider for InventoryService."""
    return InventoryService(inventory_repo=inventory_repo, cache=cache)


def get_telemetry_service_dep(
    session: Session = Depends(get_sqlmodel_session_dep),
) -> TelemetryService:
    """Dependency provider for TelemetryService wired with SQLModelTelemetrySink."""
    from infrastructure.persistence.sqlmodel.telemetry_sink import SQLModelTelemetrySink
    return TelemetryService(sink=SQLModelTelemetrySink(session=session))


_telemetry_report_cache = TelemetryReportCache(default_ttl_seconds=60.0)


def get_telemetry_report_cache_dep() -> TelemetryReportCache:
    """Dependency provider for thread-safe in-memory TelemetryReportCache with 60-second TTL."""
    return _telemetry_report_cache


def get_telemetry_repository_dep(
    session: Session = Depends(get_sqlmodel_session_dep),
) -> TelemetryRepositoryPort:
    """Dependency provider for SQLModelTelemetryRepository bound to the request session."""
    from infrastructure.persistence.sqlmodel.telemetry_repo import SQLModelTelemetryRepository
    return SQLModelTelemetryRepository(session=session)


def get_telemetry_report_service_dep(
    repository: TelemetryRepositoryPort = Depends(get_telemetry_repository_dep),
    cache: TelemetryReportCache = Depends(get_telemetry_report_cache_dep),
) -> TelemetryReportService:
    """Dependency provider for TelemetryReportService orchestrating reporting and caching."""
    return TelemetryReportService(repository=repository, cache=cache)


def get_incident_csv_report_service_dep(
    cache: CachePort = Depends(get_cache_dep),
) -> IncidentCsvReportService:
    """Dependency provider for IncidentCsvReportService wired with the shared CSV analyzer."""
    from shared.analyzer.engine import analyze_csv_stream
    return IncidentCsvReportService(cache=cache, analyzer=analyze_csv_stream)


# --- Knowledge Base & RAG Dependencies ---
_knowledge_config_singleton: Optional[KnowledgeRuntimeConfig] = None
_knowledge_vector_store_singleton: Optional[VectorStorePort] = None
_knowledge_embedding_singleton: Optional[EmbeddingServicePort] = None
_knowledge_llm_singleton: Optional[LLMGenerationPort] = None


def get_knowledge_config_dep() -> KnowledgeRuntimeConfig:
    """Dependency provider for KnowledgeRuntimeConfig loaded from .env."""
    global _knowledge_config_singleton
    if _knowledge_config_singleton is None:
        _knowledge_config_singleton = KnowledgeRuntimeConfig.from_env()
    return _knowledge_config_singleton


def get_embedding_service_dep(
    config: KnowledgeRuntimeConfig = Depends(get_knowledge_config_dep),
) -> EmbeddingServicePort:
    """Dependency provider for EmbeddingServicePort (FastEmbedAdapter)."""
    global _knowledge_embedding_singleton
    if _knowledge_embedding_singleton is None:
        from infrastructure.adapters.embedding_adapter import FastEmbedAdapter
        _knowledge_embedding_singleton = FastEmbedAdapter(config=config)
    return _knowledge_embedding_singleton


def get_vector_store_dep(
    embedder: EmbeddingServicePort = Depends(get_embedding_service_dep),
    config: KnowledgeRuntimeConfig = Depends(get_knowledge_config_dep),
) -> VectorStorePort:
    """Dependency provider for VectorStorePort (QdrantVectorStoreAdapter).

    Automatically seeds the canonical 4 corporate policy documents on first initialization
    when the collection is empty so the API is immediately ready in dev/CI environments.
    """
    global _knowledge_vector_store_singleton
    if _knowledge_vector_store_singleton is None:
        import dataclasses
        from pathlib import Path
        from application.services.chunking import MarkdownSemanticChunker
        from infrastructure.adapters.qdrant_vector_store_adapter import QdrantVectorStoreAdapter

        adapter = QdrantVectorStoreAdapter(config=config)
        adapter.ensure_collection()
        health = adapter.get_health_status()
        if health.get("indexed_points_count", 0) == 0:
            repo_root = Path(__file__).resolve().parent.parent.parent.parent
            docs_dir = repo_root / "docs" / "company-knowledge-base"
            if docs_dir.exists():
                chunker = MarkdownSemanticChunker()
                _, chunks = chunker.load_and_chunk_directory(docs_dir)
                vectors = embedder.embed_documents([c.text for c in chunks])
                embedded_chunks = [
                    dataclasses.replace(c, vector=v) for c, v in zip(chunks, vectors)
                ]
                adapter.upsert_chunks(embedded_chunks)
        _knowledge_vector_store_singleton = adapter
    return _knowledge_vector_store_singleton


def get_llm_generation_dep(
    config: KnowledgeRuntimeConfig = Depends(get_knowledge_config_dep),
) -> LLMGenerationPort:
    """Dependency provider for LLMGenerationPort (GroundedGenerationAdapter)."""
    global _knowledge_llm_singleton
    if _knowledge_llm_singleton is None:
        from infrastructure.adapters.grounded_generation_adapter import GroundedGenerationAdapter
        _knowledge_llm_singleton = GroundedGenerationAdapter(config=config)
    return _knowledge_llm_singleton


def get_knowledge_service_dep(
    vector_store: VectorStorePort = Depends(get_vector_store_dep),
    embedding_service: EmbeddingServicePort = Depends(get_embedding_service_dep),
    llm_generator: LLMGenerationPort = Depends(get_llm_generation_dep),
    config: KnowledgeRuntimeConfig = Depends(get_knowledge_config_dep),
) -> KnowledgeService:
    """Dependency provider for KnowledgeService orchestrating RAG retrieval and synthesis."""
    return KnowledgeService(
        vector_store=vector_store,
        embedding_service=embedding_service,
        llm_generator=llm_generator,
        config=config,
    )


# --- Support Agent with LangGraph & Agent Memory Dependencies ---
_agent_trace_registry_singleton: Optional[TraceRegistryPort] = None
_support_ticket_tool_singleton: Optional[SupportTicketToolPort] = None
_inventory_stock_tool_singleton: Optional[InventoryStockToolPort] = None
_agent_memory_repo_singleton: Optional[AgentMemoryRepositoryPort] = None
_memory_audit_log_repo_singleton: Optional[MemoryAuditLogRepositoryPort] = None
_memory_guardrail_singleton: Optional[MemoryGuardrailPort] = None
_user_intent_classifier_singleton: Optional[UserIntentClassifierPort] = None
_agent_memory_service_singleton: Optional[Any] = None
_support_agent_service_singleton: Optional[SupportAgentServicePort] = None


def get_trace_registry() -> TraceRegistryPort:
    """Dependency provider for the shared thread-safe in-memory TraceRegistry."""
    global _agent_trace_registry_singleton
    if _agent_trace_registry_singleton is None:
        _agent_trace_registry_singleton = TraceRegistry()
    return _agent_trace_registry_singleton


get_trace_registry_dep = get_trace_registry


def get_agent_memory_repository_dep() -> AgentMemoryRepositoryPort:
    """Dependency provider for AgentMemoryRepositoryPort (TinyDBAgentMemoryRepository)."""
    global _agent_memory_repo_singleton
    if _agent_memory_repo_singleton is None:
        from infrastructure.persistence.tinydb.agent_memory_repository import (
            TinyDBAgentMemoryRepository,
        )

        _agent_memory_repo_singleton = TinyDBAgentMemoryRepository()
    return _agent_memory_repo_singleton


def get_memory_audit_log_repository_dep() -> MemoryAuditLogRepositoryPort:
    """Dependency provider for MemoryAuditLogRepositoryPort (TinyDBMemoryAuditLogRepository)."""
    global _memory_audit_log_repo_singleton
    if _memory_audit_log_repo_singleton is None:
        from infrastructure.persistence.tinydb.memory_audit_log_repository import (
            TinyDBMemoryAuditLogRepository,
        )

        _memory_audit_log_repo_singleton = TinyDBMemoryAuditLogRepository()
    return _memory_audit_log_repo_singleton


def get_memory_guardrail_dep() -> MemoryGuardrailPort:
    """Dependency provider for MemoryGuardrailPort (MemoryGuardrailValidator)."""
    global _memory_guardrail_singleton
    if _memory_guardrail_singleton is None:
        from application.services.memory_guardrails import MemoryGuardrailValidator

        _memory_guardrail_singleton = MemoryGuardrailValidator()
    return _memory_guardrail_singleton


def get_user_intent_classifier_dep() -> UserIntentClassifierPort:
    """Dependency provider for UserIntentClassifierPort (UserIntentClassifier)."""
    global _user_intent_classifier_singleton
    if _user_intent_classifier_singleton is None:
        from application.services.memory_service import UserIntentClassifier

        _user_intent_classifier_singleton = UserIntentClassifier()
    return _user_intent_classifier_singleton


def get_agent_memory_service_dep(
    memory_repo: AgentMemoryRepositoryPort = Depends(get_agent_memory_repository_dep),
    audit_repo: MemoryAuditLogRepositoryPort = Depends(
        get_memory_audit_log_repository_dep
    ),
    guardrail_validator: MemoryGuardrailPort = Depends(get_memory_guardrail_dep),
    intent_classifier: UserIntentClassifierPort = Depends(
        get_user_intent_classifier_dep
    ),
) -> Any:
    """Dependency provider for AgentMemoryService orchestrating proposal lifecycle, recall, and consolidation."""
    global _agent_memory_service_singleton
    if _agent_memory_service_singleton is None:
        from application.services.memory_service import AgentMemoryService

        _agent_memory_service_singleton = AgentMemoryService(
            memory_repository=memory_repo,
            audit_repository=audit_repo,
            guardrail_validator=guardrail_validator,
            intent_classifier=intent_classifier,
        )
    return _agent_memory_service_singleton


def get_support_ticket_tool_dep(
    config: KnowledgeRuntimeConfig = Depends(get_knowledge_config_dep),
) -> SupportTicketToolPort:
    """Dependency provider for SupportTicketToolPort (McpTicketToolAdapter)."""
    global _support_ticket_tool_singleton
    if _support_ticket_tool_singleton is None:
        from infrastructure.adapters.mcp_ticket_tool_adapter import (
            McpTicketToolAdapter,
        )

        _support_ticket_tool_singleton = McpTicketToolAdapter(config=config)
    return _support_ticket_tool_singleton


def get_inventory_stock_tool_dep(
    config: KnowledgeRuntimeConfig = Depends(get_knowledge_config_dep),
) -> InventoryStockToolPort:
    """Dependency provider for InventoryStockToolPort (InventoryStockQueryToolAdapter)."""
    global _inventory_stock_tool_singleton
    if _inventory_stock_tool_singleton is None:
        from infrastructure.adapters.inventory_stock_tool_adapter import (
            InventoryStockQueryToolAdapter,
        )

        _inventory_stock_tool_singleton = InventoryStockQueryToolAdapter(config=config)
    return _inventory_stock_tool_singleton


def get_support_agent_service(
    vector_store: VectorStorePort = Depends(get_vector_store_dep),
    embedding_service: EmbeddingServicePort = Depends(get_embedding_service_dep),
    llm_generator: LLMGenerationPort = Depends(get_llm_generation_dep),
    ticket_tool: SupportTicketToolPort = Depends(get_support_ticket_tool_dep),
    inventory_tool: InventoryStockToolPort = Depends(get_inventory_stock_tool_dep),
    trace_registry: TraceRegistryPort = Depends(get_trace_registry),
    memory_service: Any = Depends(get_agent_memory_service_dep),
    config: KnowledgeRuntimeConfig = Depends(get_knowledge_config_dep),
) -> SupportAgentServicePort:
    """Dependency provider for SupportAgentService with compiled LangGraph state machine."""
    global _support_agent_service_singleton
    if _support_agent_service_singleton is None:
        _support_agent_service_singleton = SupportAgentService(
            vector_store=vector_store,
            embedding_service=embedding_service,
            llm_generator=llm_generator,
            ticket_tool=ticket_tool,
            inventory_tool=inventory_tool,
            trace_registry=trace_registry,
            memory_service=memory_service,
            config=config,
        )
    return _support_agent_service_singleton


get_support_agent_service_dep = get_support_agent_service


# --- Password Reset Collaborators ---
def get_password_reset_token_repository_dep(
    db: TinyDB = Depends(get_tinydb_dep),
) -> "TinyDBPasswordResetTokenRepository":
    """Dependency provider for the password reset token repository."""
    from infrastructure.adapters.tiny_db_repository import TinyDBPasswordResetTokenRepository
    return TinyDBPasswordResetTokenRepository(db)


def get_audit_log_repository_dep(
    db: TinyDB = Depends(get_tinydb_dep),
) -> "TinyDBAuditLogRepository":
    """Dependency provider for the security audit log repository."""
    from infrastructure.adapters.tiny_db_repository import TinyDBAuditLogRepository
    return TinyDBAuditLogRepository(db)


def get_email_service_dep() -> "EmailService":
    """Dependency provider for the transactional email service."""
    from application.services.email_service import EmailService
    return EmailService()


def get_rate_limiter_dep() -> "RateLimiter":
    """Dependency provider for the password reset rate limiter (fresh instance per request)."""
    from infrastructure.middleware.rate_limiter import RateLimiter
    return RateLimiter()


# --- Authentication & Authorization Guards ---
def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_service: UserService = Depends(get_user_service_dep),
    security_adapter: SecurityPort = Depends(get_security_adapter_dep),
) -> User:
    """Extract and validate the currently authenticated user from Bearer JWT."""
    try:
        user_id = security_adapter.decode_access_token(token)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Enforce administrator role permissions for guarded endpoints."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Admin role required.",
        )
    return current_user


__all__ = [
    "get_agent_memory_repository_dep",
    "get_agent_memory_service_dep",
    "get_audit_log_repository_dep",
    "get_auth_service_dep",
    "get_cache_dep",
    "get_current_admin_user",
    "get_current_user",
    "get_email_service_dep",
    "get_embedding_service_dep",
    "get_incident_csv_report_service_dep",
    "get_incident_repository_dep",
    "get_incident_service_dep",
    "get_inventory_repository_dep",
    "get_inventory_service_dep",
    "get_knowledge_config_dep",
    "get_knowledge_service_dep",
    "get_llm_generation_dep",
    "get_memory_audit_log_repository_dep",
    "get_memory_guardrail_dep",
    "get_password_reset_token_repository_dep",
    "get_profile_repository_dep",
    "get_profile_service_dep",
    "get_rate_limiter_dep",
    "get_security_adapter_dep",
    "get_sqlmodel_session_dep",
    "get_supplier_repository_dep",
    "get_supplier_service_dep",
    "get_support_agent_service",
    "get_support_agent_service_dep",
    "get_support_ticket_tool_dep",
    "get_inventory_stock_tool_dep",
    "get_telemetry_report_cache_dep",
    "get_telemetry_report_service_dep",
    "get_telemetry_repository_dep",
    "get_telemetry_service_dep",
    "get_tinydb_dep",
    "get_trace_registry",
    "get_trace_registry_dep",
    "get_user_intent_classifier_dep",
    "get_user_repository_dep",
    "get_user_service_dep",
    "get_vector_store_dep",
    "oauth2_scheme",
]
