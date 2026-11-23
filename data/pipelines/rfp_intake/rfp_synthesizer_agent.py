"""Synthesizer Agent for policy cross-checks, sales briefing, and Part 2 handoff generation."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from domain.rfp.entities import (
    DepartmentSection,
    IntakeHandoffPayload,
    InternalContact,
    RFPMetadata,
    SalesSynthesis,
)


class RFPSynthesizerAgent:
    """Consolidates department outputs, checks corporate policies, and compiles Part 2 handoff."""

    def synthesize(
        self,
        ticket_id: UUID,
        metadata: RFPMetadata,
        sections: List[DepartmentSection],
        markdown_content: str,
    ) -> IntakeHandoffPayload:
        """Cross-check findings against corporate policies and create immutable handoff payload.

        Args:
            ticket_id: Unique intake ticket identifier.
            metadata: Extracted commercial metadata.
            sections: Active department worker outputs.
            markdown_content: Converted document text.

        Returns:
            Canonical IntakeHandoffPayload instance.
        """
        text = markdown_content or ""
        lower = text.lower()

        flagged_contradictions: List[str] = []
        key_questions: List[str] = []

        # 1. Evaluate policy contradictions
        # Policy A: Turnaround < 48 hours for returns
        if "reverse" in metadata.departments_needed:
            if any(term in lower for term in ["24h", "24 horas", "inmediato", "same day"]) and "devoluc" in lower:
                flagged_contradictions.append(
                    "Conflicto de Política: El cliente solicita procesamiento de devoluciones en 24h. "
                    "La política de TrackFlow (Sofía Ramos) establece un mínimo de 48h para recepción, inspección manual y clasificación."
                )

        # Policy B: Warehouse volume > 20,000 / capacity limit
        if metadata.monthly_volume and metadata.monthly_volume > 20000:
            flagged_contradictions.append(
                f"Alerta de Capacidad: Volumen proyectado ({metadata.monthly_volume} pedidos/mes) excede el umbral "
                "de operación estándar. Requiere validación de capacidad de turnos de Ana Whitfield antes de cotizar."
            )

        # Policy C: Currency Alignment
        if metadata.client_country == "ES" and metadata.currency != "EUR":
            flagged_contradictions.append(
                "Inconsistencia Comercial: Operación en España cotizada en divisa distinta a EUR."
            )
        elif metadata.client_country == "US" and metadata.currency != "USD":
            flagged_contradictions.append(
                "Inconsistencia Comercial: Operación en Estados Unidos cotizada en divisa distinta a USD."
            )

        # Policy D: Cross-border returns
        if "internacional" in lower and "devoluc" in lower:
            flagged_contradictions.append(
                "Restricción de Política: Las devoluciones internacionales no están cubiertas por el flujo automático "
                "estándar y requieren cotización y operativa ad-hoc."
            )

        # Policy E: Unsupported services
        if metadata.unsupported_services:
            for unsup in metadata.unsupported_services:
                flagged_contradictions.append(
                    f"Servicio no soportado solicitado: '{unsup}'. TrackFlow no ofrece este servicio de forma nativa."
                )

        # 2. Consolidate questions for prospect from all active department sections
        for section in sections:
            for q in section.open_questions:
                if q not in key_questions:
                    key_questions.append(q)

        # 3. Formulate Internal Contacts
        internal_contacts = [
            InternalContact(
                name="Miguel Torres",
                role="Director Comercial / Account Lead",
                department="Ventas y Alianzas",
            ),
        ]
        if "warehouse" in metadata.departments_needed:
            internal_contacts.append(
                InternalContact(
                    name="Ana Whitfield",
                    role="Gerente de Operaciones de Almacén",
                    department="Operaciones de Almacén",
                )
            )
        if "lastmile" in metadata.departments_needed:
            internal_contacts.append(
                InternalContact(
                    name="Carlos Vega",
                    role="Coordinador de Transporte",
                    department="Transporte y Última Milla",
                )
            )
        if "reverse" in metadata.departments_needed:
            internal_contacts.append(
                InternalContact(
                    name="Sofía Ramos",
                    role="Gerente de Devoluciones",
                    department="Logística Inversa y Devoluciones",
                )
            )

        # 4. Compile Executive Summary for Sales
        active_dept_names = [s.department_name for s in sections]
        currency_symbol = "€" if metadata.currency == "EUR" else "$"
        vol_str = f"{metadata.monthly_volume:,} pedidos/mes" if metadata.monthly_volume else "Volumen no especificado"

        summary_lines = [
            f"### Resumen Ejecutivo de Análisis de Propuesta: {metadata.client_name}",
            f"- **País de Operación**: {metadata.client_country} ({'España' if metadata.client_country == 'ES' else 'Estados Unidos'})",
            f"- **Moneda Operativa**: {metadata.currency} ({currency_symbol})",
            f"- **Volumen Estimado**: {vol_str}",
            f"- **Departamentos Requeridos**: {', '.join(active_dept_names) if active_dept_names else 'Solo Almacén'}",
            "",
            "#### Puntos Clave de la Evaluación",
            f"La propuesta de {metadata.client_name} ha sido clasificada con éxito como RFP legítima. "
            f"Los departamentos involucrados ({', '.join(metadata.departments_needed)}) han evaluado el alcance "
            f"identificando {len(key_questions)} preguntas abiertas críticas que deben aclararse con el cliente "
            f"para evitar desviaciones en la propuesta comercial (Parte 2).",
        ]
        if flagged_contradictions:
            summary_lines.append("")
            summary_lines.append("#### Contradicciones y Advertencias de Política Detectadas:")
            for contra in flagged_contradictions:
                summary_lines.append(f"- ⚠️ {contra}")

        executive_summary = "\n".join(summary_lines)

        # 5. Build full handoff JSON conforming to handoff-payload-schema.json
        department_aspects_dict: Dict[str, Any] = {}
        for section in sections:
            department_aspects_dict[section.department_id] = {
                "department_id": section.department_id,
                "department_name": section.department_name,
                "responsible_person": section.responsible_person,
                "key_aspects": section.key_aspects,
                "open_questions": section.open_questions,
                "policy_warnings": section.policy_warnings,
            }

        readability_dict = {
            "flesch_reading_ease": metadata.readability_scores.flesch_reading_ease,
            "flesch_kincaid_grade": metadata.readability_scores.flesch_kincaid_grade,
            "reading_level_label": metadata.readability_scores.reading_level_label,
            "word_count": metadata.readability_scores.word_count,
            "sentence_count": metadata.readability_scores.sentence_count,
        }

        metadata_dict = {
            "client_name": metadata.client_name,
            "client_country": metadata.client_country,
            "currency": metadata.currency,
            "services_requested": metadata.services_requested,
            "monthly_volume": metadata.monthly_volume,
            "deadline": metadata.deadline,
            "budget_range": metadata.budget_range,
            "departments_needed": metadata.departments_needed,
            "unsupported_services": metadata.unsupported_services,
            "readability_scores": readability_dict,
        }

        now_iso = datetime.now(timezone.utc).isoformat()
        full_handoff_json = {
            "ticket_id": str(ticket_id),
            "schema_version": "1.0.0",
            "metadata": metadata_dict,
            "department_aspects": department_aspects_dict,
            "sales_synthesis": {
                "executive_summary": executive_summary,
                "flagged_contradictions": flagged_contradictions,
                "key_questions_for_prospect": key_questions,
                "internal_contacts": [
                    {"name": c.name, "role": c.role, "department": c.department}
                    for c in internal_contacts
                ],
            },
            "emitted_at": now_iso,
        }

        return IntakeHandoffPayload(
            id=uuid4(),
            ticket_id=ticket_id,
            schema_version="1.0.0",
            executive_summary=executive_summary,
            flagged_contradictions=flagged_contradictions,
            key_questions_for_prospect=key_questions,
            internal_contacts=internal_contacts,
            full_handoff_json=full_handoff_json,
            created_at=datetime.now(timezone.utc),
        )
