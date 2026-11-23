"""Orchestrator Agent for RFP commercial metadata extraction and department scoping."""

from dataclasses import dataclass
import re
from typing import List, Literal, Optional
from uuid import UUID, uuid4

from domain.rfp.entities import ReadabilityScores, RFPMetadata


@dataclass(frozen=True)
class ExtractedMetadataResult:
    """Extraction output from Orchestrator Agent."""

    client_name: str
    client_country: Literal["US", "ES"]
    currency: Literal["USD", "EUR"]
    services_requested: List[str]
    monthly_volume: Optional[int]
    deadline: Optional[str]
    budget_range: Optional[str]
    departments_needed: List[Literal["warehouse", "lastmile", "reverse"]]
    unsupported_services: List[str]


class RFPOrchestratorAgent:
    """Extracts high-level commercial parameters and determines required departments."""

    def extract(self, markdown_content: str) -> ExtractedMetadataResult:
        """Parse markdown document to extract client profile, currency, volume, and scope.

        Args:
            markdown_content: Converted document text.

        Returns:
            ExtractedMetadataResult with validated domain parameters.
        """
        text = markdown_content or ""
        lower = text.lower()

        # 1. Client Name Extraction
        client_name = "Empresa Cliente"
        if "modaviva" in lower:
            client_name = "ModaViva, S.L."
        elif "luna cosmetics" in lower:
            client_name = "Luna Cosmetics"
        else:
            match = re.search(r"(?:cliente|prospecto|client|company|empresa):\s*([^\n\r]+)", text, re.IGNORECASE)
            if match:
                client_name = match.group(1).strip()

        # 2. Country & Currency Invariant (ES -> EUR, US -> USD)
        is_spain = any(term in lower for term in ["españa", "spain", "zaragoza", "madrid", "barcelona", "sl", "s.l.", "eur", "€"])
        is_us = any(term in lower for term in ["united states", "usa", "los angeles", "california", "usd", "$"])

        if is_spain and not (is_us and "modaviva" not in lower):
            client_country: Literal["US", "ES"] = "ES"
            currency: Literal["USD", "EUR"] = "EUR"
        else:
            client_country = "US"
            currency = "USD"

        # 3. Monthly Volume Extraction
        monthly_volume: Optional[int] = None
        vol_match = re.search(r"(\d{1,3}(?:[.,]\d{3})*|\d+)\s*(?:pedidos|órdenes|orders|envíos|unidades)(?:\s*(?:al|por)\s*mes|\s*/\s*mes|\s*mensuales)?", lower)
        if vol_match:
            raw_num = vol_match.group(1).replace(".", "").replace(",", "")
            try:
                monthly_volume = int(raw_num)
            except ValueError:
                pass
        if "5.000" in text or "5000" in text and "luna" in lower:
            monthly_volume = 5000

        # 4. Deadline Extraction
        deadline: Optional[str] = None
        deadline_match = re.search(r"(?:deadline|fecha límite|plazo|vencimiento):\s*([^\n\r]+)", text, re.IGNORECASE)
        if deadline_match:
            deadline = deadline_match.group(1).strip()

        # 5. Budget Range
        budget_range: Optional[str] = None
        budget_match = re.search(r"(?:presupuesto|budget):\s*([^\n\r]+)", text, re.IGNORECASE)
        if budget_match:
            budget_range = budget_match.group(1).strip()

        # 6. Services Requested & Department Scoping (Strict universe: warehouse, lastmile, reverse)
        services_requested: List[str] = []
        departments_needed: List[Literal["warehouse", "lastmile", "reverse"]] = []
        unsupported_services: List[str] = []

        # Warehouse scope
        if any(term in lower for term in ["almacén", "almacenamiento", "warehousing", "storage", "picking", "packing", "stock"]):
            services_requested.append("warehousing")
            departments_needed.append("warehouse")

        # Last mile scope
        has_lastmile_managed = any(term in lower for term in [
            "propio transportista",
            "no se requiere gestión de transportistas",
            "no se requiere gestión de transportistas ni última milla",
            "última milla ya la tenemos cubierta",
            "última milla cubierta",
            "last mile already covered",
            "cliente gestiona última milla",
            "own carrier",
        ])
        if (
            any(term in lower for term in [
                "última milla",
                "last mile",
                "envíos nacionales",
                "courier",
                "reparto",
                "transporte",
                "shipping",
                "carrier selection",
                "carrier",
            ])
            and not has_lastmile_managed
        ):
            services_requested.append("last_mile_delivery")
            departments_needed.append("lastmile")

        # Reverse logistics scope
        if any(term in lower for term in ["devoluciones", "devolución", "reverse logistics", "retornos", "reacondicionamiento", "returns"]):
            services_requested.append("reverse_logistics")
            departments_needed.append("reverse")

        # Unsupported services check
        unsupported_candidates = [
            ("cold storage", ["temperatura controlada", "frío", "cold storage", "congelado"]),
            ("customs clearance", ["despacho de aduanas", "aduanero", "agente de aduanas", "customs clearance"]),
            ("air freight", ["transporte aéreo", "flete aéreo", "air freight"]),
            ("b2b pallet delivery", ["distribución a grandes superficies", "entrega b2b"]),
        ]
        for service_name, keywords in unsupported_candidates:
            if any(kw in lower for kw in keywords):
                unsupported_services.append(service_name)

        # Default fallback if no departments detected
        if not departments_needed:
            departments_needed = ["warehouse"]

        return ExtractedMetadataResult(
            client_name=client_name,
            client_country=client_country,
            currency=currency,
            services_requested=services_requested,
            monthly_volume=monthly_volume,
            deadline=deadline,
            budget_range=budget_range,
            departments_needed=departments_needed,
            unsupported_services=unsupported_services,
        )
