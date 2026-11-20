"""Inventory application Data Transfer Objects (DTOs).

Re-exports from canonical schemas.py for architectural consistency.
"""

from schemas import (
    InboundOrderCreateDTO,
    OrderResponseDTO,
    OutboundOrderCreateDTO,
    ProductCreateDTO,
    ProductResponseDTO,
)

__all__ = [
    "InboundOrderCreateDTO",
    "OrderResponseDTO",
    "OutboundOrderCreateDTO",
    "ProductCreateDTO",
    "ProductResponseDTO",
]
