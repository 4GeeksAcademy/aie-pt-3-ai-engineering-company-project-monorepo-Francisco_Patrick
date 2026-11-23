"""Department worker agents: Warehouse, Last Mile, and Reverse Logistics."""

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4

from domain.rfp.entities import DepartmentSection


class BaseDepartmentWorker:
    """Base class for domain department workers."""

    department_id: Literal["warehouse", "lastmile", "reverse"]
    department_name: str
    responsible_person: str


class WarehouseWorker(BaseDepartmentWorker):
    """Evaluates warehousing, storage requirements, handling constraints, and onboarding complexity."""

    department_id: Literal["warehouse", "lastmile", "reverse"] = "warehouse"
    department_name: str = "Operaciones de Almacén"
    responsible_person: str = "Ana Whitfield"

    def analyze(self, ticket_id: UUID, markdown_content: str, country: str) -> DepartmentSection:
        """Analyze warehouse requirements adhering to zero-hallucination guardrail."""
        text = markdown_content or ""
        lower = text.lower()

        open_questions: List[str] = []
        policy_warnings: List[str] = []
        key_aspects: Dict[str, Any] = {}

        # 1. Location preference
        if country == "ES" or "zaragoza" in lower or "españa" in lower:
            location_pref = "Zaragoza"
        elif "los angeles" in lower or "california" in lower or country == "US":
            location_pref = "Los Ángeles"
        else:
            location_pref = "Ambos"
        key_aspects["warehouse_location_preference"] = location_pref

        # 2. Pallet storage required (Zero Hallucination: do NOT invent pallet numbers)
        pallet_match = None
        # look for explicit pallet numbers
        import re
        p_match = re.search(r"(\d+)\s*(?:pallets?|palets?|posiciones)", lower)
        if p_match:
            pallet_storage = int(p_match.group(1))
            key_aspects["pallet_storage_required"] = pallet_storage
        else:
            key_aspects["pallet_storage_required"] = None
            open_questions.append(
                "Número exacto de pallets o posiciones de estantería requeridas no especificado en la propuesta."
            )

        # 3. SKU Count
        sku_match = re.search(r"(\d+)\s*(?:skus?|referencias)", lower)
        if sku_match:
            key_aspects["sku_count"] = int(sku_match.group(1))
        else:
            key_aspects["sku_count"] = None
            open_questions.append(
                "Volumen o catálogo total de SKUs activos y dimensiones unitarias no especificados."
            )

        # 4. Special Handling
        special_handling: List[str] = []
        if any(term in lower for term in ["fragile", "frágil", "delicado", "cristal"]):
            special_handling.append("fragile_handling")
        if any(term in lower for term in ["cosmetics", "cosmética", "belleza", "lotion", "serum"]):
            special_handling.append("cosmetics_storage")
        if any(term in lower for term in ["moda", "fashion", "ropa", "textil", "prendas"]):
            special_handling.append("fashion_garments")
        key_aspects["special_handling"] = special_handling

        # 5. Onboarding Complexity
        if "garaje" in lower or "garage" in lower:
            key_aspects["onboarding_complexity"] = "Alta"
            open_questions.append(
                "Transición desde garaje/espacio informal requiere inventario inicial ciego y estandarización de etiquetado."
            )
        elif len(special_handling) > 1:
            key_aspects["onboarding_complexity"] = "Media"
        else:
            key_aspects["onboarding_complexity"] = "Baja"

        # Check volume capacity rule (> 20,000 orders/month)
        vol_match = re.search(r"(\d+)\s*(?:pedidos|órdenes)", lower)
        if vol_match and int(vol_match.group(1)) > 20000:
            policy_warnings.append(
                "Volumen superior a 20.000 pedidos/mes requiere validación de capacidad de turnos con Ana Whitfield."
            )

        return DepartmentSection(
            id=uuid4(),
            ticket_id=ticket_id,
            department_id="warehouse",
            department_name=self.department_name,
            responsible_person=self.responsible_person,
            key_aspects=key_aspects,
            open_questions=open_questions,
            policy_warnings=policy_warnings,
        )


class LastMileWorker(BaseDepartmentWorker):
    """Evaluates delivery carrier strategy, SLAs, and geographic coverage."""

    department_id: Literal["warehouse", "lastmile", "reverse"] = "lastmile"
    department_name: str = "Transporte y Última Milla"
    responsible_person: str = "Carlos Vega"

    def analyze(self, ticket_id: UUID, markdown_content: str, country: str) -> DepartmentSection:
        """Analyze last mile delivery requirements adhering to zero-hallucination guardrail."""
        text = markdown_content or ""
        lower = text.lower()

        open_questions: List[str] = []
        policy_warnings: List[str] = []
        key_aspects: Dict[str, Any] = {}

        # 1. Carrier Strategy
        key_aspects["carrier_strategy"] = "TrackFlow Network"

        # 2. Geographic scope
        if country == "ES":
            geo = "Domestic ES"
        elif country == "US":
            geo = "Domestic US"
        else:
            geo = "Cross-Border"
        key_aspects["geographic_scope"] = geo

        # 3. Delivery SLA requested
        import re
        sla_match = re.search(r"(?:sla|entrega|plazo de entrega)[^\n\r.]*?(\d{1,2}(?:-\d{1,2})?\s*(?:h|horas|días|dias))", lower)
        if sla_match:
            key_aspects["delivery_sla_requested"] = sla_match.group(1).strip()
        else:
            key_aspects["delivery_sla_requested"] = None
            open_questions.append(
                "SLA de entrega esperado (estándar 3-5 días vs express 24-48h) no indicado en el documento."
            )

        # 4. Special delivery requirements
        special_reqs: List[str] = []
        if "signature" in lower or "firma" in lower:
            special_reqs.append("signature_on_delivery")
        if "cash on delivery" in lower or "contra reembolso" in lower:
            special_reqs.append("cash_on_delivery")
            policy_warnings.append("TrackFlow no gestiona contra reembolso de forma estándar.")
        key_aspects["special_delivery_requirements"] = special_reqs

        return DepartmentSection(
            id=uuid4(),
            ticket_id=ticket_id,
            department_id="lastmile",
            department_name=self.department_name,
            responsible_person=self.responsible_person,
            key_aspects=key_aspects,
            open_questions=open_questions,
            policy_warnings=policy_warnings,
        )


class ReverseWorker(BaseDepartmentWorker):
    """Evaluates return window, inspection workflow, and disposition rules."""

    department_id: Literal["warehouse", "lastmile", "reverse"] = "reverse"
    department_name: str = "Logística Inversa y Devoluciones"
    responsible_person: str = "Sofía Ramos"

    def analyze(self, ticket_id: UUID, markdown_content: str, country: str) -> DepartmentSection:
        """Analyze reverse logistics requirements adhering to zero-hallucination guardrail."""
        text = markdown_content or ""
        lower = text.lower()

        open_questions: List[str] = []
        policy_warnings: List[str] = []
        key_aspects: Dict[str, Any] = {}

        # 1. Return window
        import re
        win_match = re.search(r"(\d+)\s*(?:días|dias|days)\s*(?:de devolución|para devolver|return window)", lower)
        if win_match:
            key_aspects["return_window_days"] = int(win_match.group(1))
        else:
            key_aspects["return_window_days"] = 30  # TrackFlow standard policy default

        # 2. Return rate
        rate_match = re.search(r"(\d{1,2}(?:[.,]\d+)?)\s*%\s*(?:devolucion|devoluciones|returns|tasa)", lower)
        if rate_match:
            val = float(rate_match.group(1).replace(",", ".")) / 100.0
            key_aspects["estimated_return_rate"] = val
        else:
            key_aspects["estimated_return_rate"] = None
            open_questions.append(
                "Tasa estimada de devoluciones esperada no informada (se asume estándar de moda 15-25% a validar)."
            )

        # 3. Inspection required
        key_aspects["inspection_required"] = True
        key_aspects["disposition_flow"] = ["reventa", "reacondicionamiento", "descarte"]

        # Policy checks
        if (
            any(term in lower for term in ["24h", "24 horas", "inmediato", "mismo día", "same day"])
            and any(term in lower for term in ["reacondicion", "devolución", "retorno", "return", "returns", "exchange", "turnaround"])
        ):
            policy_warnings.append(
                "Reacondicionamiento o turnaround en < 48h entra en conflicto con la política de inspección manual de Sofía Ramos."
            )

        if "internacional" in lower and "devoluc" in lower:
            policy_warnings.append(
                "Devoluciones internacionales requieren gestión y acuerdo específico con Sofía Ramos."
            )

        return DepartmentSection(
            id=uuid4(),
            ticket_id=ticket_id,
            department_id="reverse",
            department_name=self.department_name,
            responsible_person=self.responsible_person,
            key_aspects=key_aspects,
            open_questions=open_questions,
            policy_warnings=policy_warnings,
        )
