"""Services level schemas re-export facade."""

import os
import sys

_API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "api"))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from services.api.schemas import (
    InboundOrderCreate,
    InboundOrderCreateDTO,
    OrderResponse,
    OrderResponseDTO,
    OutboundOrderCreate,
    OutboundOrderCreateDTO,
    ProductBase,
    ProductCreate,
    ProductCreateDTO,
    ProductResponse,
    ProductResponseDTO,
    SKUCreate,
    SKUResponse,
    StockEntryCreate,
    StockEntryResponse,
    StockExitCreate,
    StockExitResponse,
)

__all__ = [
    "InboundOrderCreate",
    "InboundOrderCreateDTO",
    "OrderResponse",
    "OrderResponseDTO",
    "OutboundOrderCreate",
    "OutboundOrderCreateDTO",
    "ProductBase",
    "ProductCreate",
    "ProductCreateDTO",
    "ProductResponse",
    "ProductResponseDTO",
    "SKUCreate",
    "SKUResponse",
    "StockEntryCreate",
    "StockEntryResponse",
    "StockExitCreate",
    "StockExitResponse",
]
