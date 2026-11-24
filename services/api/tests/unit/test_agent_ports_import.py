"""Unit tests validating import integrity and type annotation evaluation for domain.agent.ports.

Guards against NameErrors caused by missing typing imports or deferred annotation issues
(e.g., Sequence in InputGuardrailPort.evaluate_input).
"""

import inspect
import typing
from typing import Any, Optional, Sequence

import domain.agent.ports as agent_ports
from domain.agent.ports import (
    AgentMemoryRepositoryPort,
    AuthorizationGuardrailPort,
    ContextSanitizerPort,
    GuardrailObservabilityPort,
    InputGuardrailPort,
    InventoryStockToolPort,
    MemoryAuditLogRepositoryPort,
    MemoryGuardrailPort,
    OutputGuardrailPort,
    SupportAgentServicePort,
    SupportTicketToolPort,
    TraceRegistryPort,
    UserIntentClassifierPort,
)


def test_input_guardrail_port_import_and_type_hints():
    """Verify InputGuardrailPort imports and evaluate_input type annotations resolve without NameError."""
    assert InputGuardrailPort is not None
    hints = typing.get_type_hints(InputGuardrailPort.evaluate_input)
    assert "conversation_history" in hints
    assert hints["conversation_history"] == Optional[Sequence[Any]]


def test_all_agent_ports_type_hints_resolve():
    """Scan all port classes in domain.agent.ports and ensure get_type_hints succeeds on all methods."""
    for name, cls in inspect.getmembers(agent_ports, inspect.isclass):
        if cls.__module__ == agent_ports.__name__:
            for method_name, method in inspect.getmembers(cls, inspect.isfunction):
                hints = typing.get_type_hints(method)
                assert isinstance(hints, dict), f"Failed to get type hints for {name}.{method_name}"
