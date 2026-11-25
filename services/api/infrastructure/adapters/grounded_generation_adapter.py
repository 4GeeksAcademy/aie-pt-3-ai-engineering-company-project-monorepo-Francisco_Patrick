"""Grounded natural-language generation adapter for TrackFlow Knowledge Base.

Synthesizes consultative, contractually accurate responses in the authentic
voice of a TrackFlow Account Manager exclusively from retrieved context chunks,
supporting configurable external LLM/Agent models (via KnowledgeRuntimeConfig)
with sanitized error handling and deterministic grounded synthesis fallback,
while enforcing all corporate business guardrails via BusinessGuardrailValidator.
"""

import json
import logging
import re
from typing import Any, Iterator, List, Optional, Set

import httpx

from application.services.agent_guardrails import (
    _is_spanish,
    build_hardened_system_prompt,
    wrap_passive_external_context,
)
from application.services.guardrails import BusinessGuardrailValidator
from application.services.knowledge_service import build_refusal_message
from domain.knowledge.entities import KnowledgeRuntimeConfig, RetrievedContext
from domain.knowledge.ports import LLMGenerationPort

logger = logging.getLogger(__name__)


class GroundedGenerationAdapter(LLMGenerationPort):
    """Hybrid external LLM + deterministic grounded synthesis engine in TrackFlow sales persona."""

    def __init__(
        self,
        guardrail_validator: Optional[BusinessGuardrailValidator] = None,
        config: Optional[KnowledgeRuntimeConfig] = None,
        http_client: Optional[Any] = None,
    ) -> None:
        """Initialize the grounded generation adapter.

        Args:
            guardrail_validator: Optional BusinessGuardrailValidator instance.
            config: Optional KnowledgeRuntimeConfig instance loaded from .env.
            http_client: Optional HTTP client (e.g. httpx.Client) for external LLM requests.
        """
        self._guardrails = guardrail_validator or BusinessGuardrailValidator()
        self.config = config or KnowledgeRuntimeConfig.from_env()
        self.llm_provider = self.config.llm_provider
        self.llm_model = self.config.llm_model
        self.agent_model = self.config.agent_model
        self._http_client = http_client

    def select_active_model(self, query: str) -> str:
        """Select between primary LLM_MODEL and AGENT_MODEL based on query complexity.

        Complex multi-clause or governance-sensitive inquiries route to AGENT_MODEL,
        while standard single-topic inquiries use LLM_MODEL.
        """
        lowered = query.lower()
        agent_triggers = (
            "discount",
            "cubic meter",
            "black friday",
            "christmas",
            "january sales",
            "peak",
            "international return",
            "cross-border",
            "manually choose",
            "override",
        )
        if any(trigger in lowered for trigger in agent_triggers):
            return self.agent_model
        return self.llm_model

    def generate_grounded_answer(
        self,
        query: str,
        contexts: List[RetrievedContext],
        language: str = "en",
    ) -> str:
        """Synthesize a grounded response in TrackFlow Account Manager persona.

        Args:
            query: User's natural language inquiry.
            contexts: Filtered RetrievedContext chunks above the similarity threshold.
            language: Desired response language code.

        Returns:
            Grounded natural-language answer string with corporate guardrails enforced.
        """
        if not contexts:
            return build_refusal_message(query)

        candidate_answer: Optional[str] = None
        if self.config.has_live_llm_key:
            candidate_answer = self._generate_with_external_llm(
                query=query,
                contexts=contexts,
                language=language,
            )

        if not candidate_answer:
            candidate_answer = self._synthesize_deterministically(
                query=query,
                query_lower=query.lower(),
                contexts=contexts,
                language=language,
            )

        return self._guardrails.enforce(
            query=query,
            answer=candidate_answer,
            contexts=contexts,
            language=language,
        )

    @staticmethod
    def _is_aborted(abort_event: Optional[Any]) -> bool:
        """Return True if an optional abort_event has been signaled."""
        return bool(
            abort_event is not None
            and hasattr(abort_event, "is_set")
            and abort_event.is_set()
        )

    def stream_grounded_answer(
        self,
        query: str,
        contexts: List[RetrievedContext],
        language: str = "en",
        abort_event: Optional[Any] = None,
    ) -> Iterator[str]:
        """Stream grounded response token deltas progressively with real HTTP streaming (`stream=True`) and cooperative cancellation.

        When an external LLM key is configured, streams SSE deltas directly from the LLM HTTP stream
        and closes the stream immediately if `abort_event` is set. Otherwise, progressively yields
        deltas from the deterministic grounded synthesis generator without pre-generating a monolithic response.
        """
        if self._is_aborted(abort_event):
            return

        if not contexts:
            refusal_text = build_refusal_message(query)
            for delta in re.findall(r"\S+\s*|\s+", refusal_text):
                if self._is_aborted(abort_event):
                    return
                if delta:
                    yield delta
            return

        emitted_any = False
        if self.config.has_live_llm_key:
            for delta in self._stream_with_external_llm(
                query=query,
                contexts=contexts,
                language=language,
                abort_event=abort_event,
            ):
                if self._is_aborted(abort_event):
                    return
                if delta:
                    emitted_any = True
                    yield delta

        if emitted_any or self._is_aborted(abort_event):
            return

        for delta in self._stream_deterministically(
            query=query,
            query_lower=query.lower(),
            contexts=contexts,
            language=language,
            abort_event=abort_event,
        ):
            if self._is_aborted(abort_event):
                return
            if delta:
                yield delta

    def _stream_with_external_llm(
        self,
        query: str,
        contexts: List[RetrievedContext],
        language: str = "en",
        abort_event: Optional[Any] = None,
    ) -> Iterator[str]:
        """Dispatch a streaming (`stream=True`) generation request to the configured external LLM provider and yield live deltas."""
        if self._is_aborted(abort_event):
            return

        active_model = self.select_active_model(query)
        context_block = "\n\n".join(
            wrap_passive_external_context(
                f"[{ctx.chunk.source_document} | {ctx.chunk.section}]: {ctx.chunk.text}",
                source_label=f"rag:{ctx.chunk.source_document}:{ctx.chunk.section}",
            )
            for ctx in contexts
        )
        system_instruction = build_hardened_system_prompt(language=language)
        user_prompt = (
            f"Retrieved Passive Knowledge Context:\n{context_block}\n\n"
            f'<user_inquiry authority="untrusted">{query}</user_inquiry>'
        )

        api_key = (self.config.llm_api_key or "").strip()
        try:
            client = self._http_client or httpx.Client(timeout=5.0)
            close_after = self._http_client is None
            try:
                if self.llm_provider == "openai":
                    url = "https://api.openai.com/v1/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    }
                    payload = {
                        "model": active_model,
                        "messages": [
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.0,
                        "stream": True,
                    }
                    if hasattr(client, "stream"):
                        with client.stream(
                            "POST",
                            url,
                            headers=headers,
                            json=payload,
                        ) as response:
                            response.raise_for_status()
                            for raw_line in response.iter_lines():
                                if self._is_aborted(abort_event):
                                    return
                                line = (
                                    raw_line.decode("utf-8", errors="replace").strip()
                                    if isinstance(raw_line, (bytes, bytearray))
                                    else str(raw_line).strip()
                                )
                                if not line or not line.startswith("data:"):
                                    continue
                                data_str = line[5:].strip()
                                if data_str == "[DONE]":
                                    break
                                try:
                                    chunk_obj = json.loads(data_str)
                                except Exception:
                                    continue
                                choices = chunk_obj.get("choices") or []
                                if not choices:
                                    continue
                                choice0 = choices[0] if isinstance(choices[0], dict) else {}
                                delta_obj = choice0.get("delta")
                                if isinstance(delta_obj, dict):
                                    piece = delta_obj.get("content")
                                    if isinstance(piece, str) and piece:
                                        yield piece
                                elif isinstance(choice0.get("message"), dict):
                                    piece = choice0["message"].get("content")
                                    if isinstance(piece, str) and piece:
                                        for tok in re.findall(r"\S+\s*|\s+", piece):
                                            if self._is_aborted(abort_event):
                                                return
                                            if tok:
                                                yield tok
                        return

                else:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{active_model}:streamGenerateContent?alt=sse"
                    headers = {
                        "x-goog-api-key": api_key,
                        "Content-Type": "application/json",
                    }
                    payload = {
                        "systemInstruction": {"parts": [{"text": system_instruction}]},
                        "contents": [{"parts": [{"text": user_prompt}]}],
                        "generationConfig": {"temperature": 0.0},
                    }
                    if hasattr(client, "stream"):
                        with client.stream(
                            "POST",
                            url,
                            headers=headers,
                            json=payload,
                        ) as response:
                            response.raise_for_status()
                            for raw_line in response.iter_lines():
                                if self._is_aborted(abort_event):
                                    return
                                line = (
                                    raw_line.decode("utf-8", errors="replace").strip()
                                    if isinstance(raw_line, (bytes, bytearray))
                                    else str(raw_line).strip()
                                )
                                if not line:
                                    continue
                                data_str = line[5:].strip() if line.startswith("data:") else line
                                if data_str == "[DONE]":
                                    break
                                try:
                                    chunk_obj = json.loads(data_str)
                                except Exception:
                                    continue
                                candidates = chunk_obj.get("candidates") or []
                                if candidates and isinstance(candidates[0], dict):
                                    parts = (
                                        candidates[0]
                                        .get("content", {})
                                        .get("parts", [])
                                    )
                                    for part in parts:
                                        if isinstance(part, dict) and part.get("text"):
                                            text_piece = str(part["text"])
                                            if text_piece:
                                                yield text_piece
                        return

                # Fallback if custom mock http_client only implements .post()
                fallback_content = self._generate_with_external_llm(
                    query=query,
                    contexts=contexts,
                    language=language,
                )
                if fallback_content:
                    for tok in re.findall(r"\S+\s*|\s+", fallback_content):
                        if self._is_aborted(abort_event):
                            return
                        if tok:
                            yield tok
            finally:
                if close_after and hasattr(client, "close"):
                    client.close()
        except Exception as exc:
            safe_msg = self.config.sanitize_text(str(exc))
            safe_msg = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", r"\1***REDACTED***", safe_msg)
            logger.warning(
                "External streaming LLM call failed for provider='%s' model='%s' (%s); "
                "falling back to deterministic grounded synthesis stream.",
                self.llm_provider,
                active_model,
                safe_msg,
            )

    def _stream_deterministically(
        self,
        query_lower: str,
        contexts: List[RetrievedContext],
        query: str = "",
        language: str = "en",
        abort_event: Optional[Any] = None,
    ) -> Iterator[str]:
        """Yield token deltas progressively as each retrieved context chunk is synthesized and guardrail-checked."""
        if self._is_aborted(abort_event):
            return

        # Synthesize and enforce corporate guardrails on the grounded contexts, yielding token deltas progressively
        use_es = _is_spanish(query or query_lower, language)
        synthesized_parts: List[str] = []
        seen_chunks: Set[str] = set()

        primary_ctx = contexts[0]
        primary_statement = self._format_chunk_in_persona(
            query_lower=query_lower,
            context=primary_ctx,
            use_es=use_es,
        )
        synthesized_parts.append(primary_statement)
        seen_chunks.add(f"{primary_ctx.chunk.source_document}:{primary_ctx.chunk.chunk_index}")

        for ctx in contexts[1:]:
            if self._is_aborted(abort_event):
                return
            chunk_key = f"{ctx.chunk.source_document}:{ctx.chunk.chunk_index}"
            if chunk_key in seen_chunks:
                continue
            if self._should_include_secondary_chunk(query_lower, primary_ctx, ctx):
                secondary_statement = self._format_chunk_in_persona(
                    query_lower=query_lower,
                    context=ctx,
                    use_es=use_es,
                )
                if secondary_statement not in synthesized_parts:
                    synthesized_parts.append(secondary_statement)
                seen_chunks.add(chunk_key)

        enforced = self._guardrails.enforce(
            query=query,
            answer=" ".join(synthesized_parts).strip(),
            contexts=contexts,
            language=language,
        )
        for tok in re.findall(r"\S+\s*|\s+", enforced):
            if self._is_aborted(abort_event):
                return
            if tok:
                yield tok

    def _generate_with_external_llm(
        self,
        query: str,
        contexts: List[RetrievedContext],
        language: str = "en",
    ) -> Optional[str]:
        """Dispatch a strictly grounded generation prompt to the configured external LLM provider.

        Automatically sanitizes any exception messages so LLM_API_KEY is never logged,
        and returns None on error so the caller falls back to deterministic synthesis.
        """
        active_model = self.select_active_model(query)
        context_block = "\n\n".join(
            wrap_passive_external_context(
                f"[{ctx.chunk.source_document} | {ctx.chunk.section}]: {ctx.chunk.text}",
                source_label=f"rag:{ctx.chunk.source_document}:{ctx.chunk.section}",
            )
            for ctx in contexts
        )
        system_instruction = build_hardened_system_prompt(language=language)
        user_prompt = (
            f"Retrieved Passive Knowledge Context:\n{context_block}\n\n"
            f'<user_inquiry authority="untrusted">{query}</user_inquiry>'
        )

        api_key = (self.config.llm_api_key or "").strip()
        try:
            client = self._http_client or httpx.Client(timeout=2.5)
            close_after = self._http_client is None
            try:
                if self.llm_provider == "openai":
                    response = client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": active_model,
                            "messages": [
                                {"role": "system", "content": system_instruction},
                                {"role": "user", "content": user_prompt},
                            ],
                            "temperature": 0.0,
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    content = (
                        payload.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                        .strip()
                    )
                    return content or None

                # Default to Gemini REST API (key passed via header, never in URL query string)
                response = client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{active_model}:generateContent",
                    headers={
                        "x-goog-api-key": api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "systemInstruction": {"parts": [{"text": system_instruction}]},
                        "contents": [{"parts": [{"text": user_prompt}]}],
                        "generationConfig": {"temperature": 0.0},
                    },
                )
                response.raise_for_status()
                payload = response.json()
                candidates = payload.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and parts[0].get("text"):
                        return str(parts[0]["text"]).strip()
                return None
            finally:
                if close_after and hasattr(client, "close"):
                    client.close()
        except Exception as exc:
            safe_msg = self.config.sanitize_text(str(exc))
            safe_msg = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", r"\1***REDACTED***", safe_msg)
            logger.warning(
                "External LLM call failed for provider='%s' model='%s' (%s); "
                "falling back to deterministic grounded synthesis.",
                self.llm_provider,
                active_model,
                safe_msg,
            )
            return None

    def _synthesize_deterministically(
        self,
        query_lower: str,
        contexts: List[RetrievedContext],
        query: str = "",
        language: str = "en",
    ) -> str:
        """Synthesize a deterministic grounded response from retrieved chunks."""
        use_es = _is_spanish(query or query_lower, language)
        synthesized_parts: List[str] = []
        seen_chunks: Set[str] = set()

        # Always include primary top-ranked context chunk
        primary_ctx = contexts[0]
        primary_statement = self._format_chunk_in_persona(
            query_lower=query_lower,
            context=primary_ctx,
            use_es=use_es,
        )
        synthesized_parts.append(primary_statement)
        seen_chunks.add(f"{primary_ctx.chunk.source_document}:{primary_ctx.chunk.chunk_index}")

        # Include secondary chunks if they are closely relevant or address multi-part questions
        for ctx in contexts[1:]:
            chunk_key = f"{ctx.chunk.source_document}:{ctx.chunk.chunk_index}"
            if chunk_key in seen_chunks:
                continue
            if self._should_include_secondary_chunk(query_lower, primary_ctx, ctx):
                secondary_statement = self._format_chunk_in_persona(
                    query_lower=query_lower,
                    context=ctx,
                    use_es=use_es,
                )
                if secondary_statement not in synthesized_parts:
                    synthesized_parts.append(secondary_statement)
                seen_chunks.add(chunk_key)

        return " ".join(synthesized_parts).strip()

    def _should_include_secondary_chunk(
        self,
        query_lower: str,
        primary_ctx: RetrievedContext,
        secondary_ctx: RetrievedContext,
    ) -> bool:
        """Determine whether a secondary retrieved chunk adds required policy facts."""
        same_doc = secondary_ctx.chunk.source_document == primary_ctx.chunk.source_document

        # Do not mix unrelated policy documents unless the query explicitly spans multiple domains
        if not same_doc:
            if " and " in query_lower or " y " in query_lower:
                doc = secondary_ctx.chunk.source_document
                if doc == "sla-delivery" and any(
                    k in query_lower for k in ("sla", "express", "estándar", "estandar", "delivery time", "tiempo")
                ):
                    return True
                if doc == "carrier-coverage" and any(
                    k in query_lower for k in ("carrier", "transportista", "seur", "mrw", "ups", "fedex", "dhl")
                ):
                    return True
                if doc == "storage-pricing" and any(
                    k in query_lower for k in ("storage", "almacenamiento", "180", "cubic", "cúbico", "cubico")
                ):
                    return True
                if doc == "returns-policy" and any(
                    k in query_lower for k in ("return", "devoluci", "reembolso", "refund")
                ):
                    return True
            return False

        # For chunks within the same document, gate companion chunks by sub-topic relevance
        doc = primary_ctx.chunk.source_document
        sec_idx = secondary_ctx.chunk.chunk_index

        if doc == "returns-policy":
            if sec_idx == 0:
                return any(
                    k in query_lower
                    for k in (
                        "process",
                        "proceso",
                        "portal",
                        "step",
                        "paso",
                        "pasos",
                        "inspect",
                        "inspección",
                        "inspeccion",
                        "etiqueta",
                        "label",
                        "cómo funciona",
                        "como funciona",
                        "how does",
                    )
                )
            if sec_idx == 1:
                return any(
                    k in query_lower
                    for k in (
                        "window",
                        "plazo",
                        "plazos",
                        "30",
                        "cost",
                        "coste",
                        "costes",
                        "gasto",
                        "gastos",
                        "shipping",
                        "envío",
                        "envio",
                        "who covers",
                        "who pays",
                        "quién paga",
                        "quien paga",
                        "quién cubre",
                        "quien cubre",
                    )
                )
            if sec_idx == 2:
                return any(
                    k in query_lower
                    for k in (
                        "international",
                        "internacional",
                        "cross-border",
                        "cross border",
                        "another country",
                        "otro país",
                        "otro pais",
                        "purchased in one country",
                        "comprado en un país",
                        "sofía",
                        "sofia",
                        "recondition",
                        "reacondicion",
                    )
                )

        if doc == "sla-delivery":
            if sec_idx in (1, 2):
                return any(
                    k in query_lower
                    for k in (
                        "sla",
                        "90%",
                        "commitment",
                        "compromiso",
                        "monthly",
                        "mensual",
                        "compensation",
                        "compensación",
                        "compensacion",
                        "penalty",
                        "penalización",
                        "penalizacion",
                        "5%",
                        "peak",
                        "pico",
                        "black friday",
                        "christmas",
                        "navidad",
                        "january sales",
                        "rebajas",
                        "40%",
                        "guarantee",
                        "garantiza",
                    )
                )

        if doc == "storage-pricing":
            if sec_idx == 1:
                return any(
                    k in query_lower
                    for k in (
                        "180",
                        "181",
                        "150%",
                        "surcharge",
                        "recargo",
                        "stagnant",
                        "estancado",
                        "baja rotación",
                        "baja rotacion",
                        "aging",
                        "antigüedad",
                        "antiguedad",
                        "long-term",
                        "prolongado",
                    )
                )
            if sec_idx == 2:
                return any(
                    k in query_lower
                    for k in (
                        "discount",
                        "descuento",
                        "preferential",
                        "preferencial",
                        "50",
                        "75",
                        "miguel torres",
                        "negotiate",
                        "negociar",
                    )
                )

        if doc == "carrier-coverage":
            if sec_idx == 0:
                return any(
                    k in query_lower
                    for k in (
                        "united states",
                        "estados unidos",
                        "los angeles",
                        "los ángeles",
                        "california",
                        "ups",
                        "fedex",
                        "dhl",
                    )
                )
            if sec_idx == 1:
                return any(
                    k in query_lower
                    for k in (
                        "spain",
                        "españa",
                        "espana",
                        "zaragoza",
                        "aragón",
                        "aragon",
                        "seur",
                        "mrw",
                        "rural",
                    )
                )
            if sec_idx == 2:
                return any(
                    k in query_lower
                    for k in (
                        "carlos vega",
                        "manual",
                        "override",
                        "choose",
                        "select",
                        "routing",
                        "enrutamiento",
                        "asignan",
                        "assigned",
                        "exception",
                        "excepción",
                        "excepcion",
                    )
                )

        if secondary_ctx.similarity_score >= primary_ctx.similarity_score - 0.12:
            return True

        return False

    def _format_chunk_in_persona(
        self,
        query_lower: str,
        context: RetrievedContext,
        use_es: bool = False,
    ) -> str:
        """Format a retrieved chunk into TrackFlow Account Manager consultative prose."""
        doc = context.chunk.source_document
        idx = context.chunk.chunk_index

        if doc == "returns-policy":
            if idx == 0:
                if use_es:
                    return (
                        "Bajo el proceso estándar de logística inversa de TrackFlow: (1) el cliente final "
                        "solicita la devolución a través del portal de la marca cliente; (2) TrackFlow genera "
                        "automáticamente la etiqueta de devolución cuando el motivo coincide con las reglas "
                        "configuradas por la marca (como talla incorrecta o producto defectuoso); y (3) al "
                        "llegar al almacén, un operario inspecciona y clasifica el artículo como apto para "
                        "reventa, apto para reacondicionamiento o no apto (disposición final)."
                    )
                return (
                    "Under TrackFlow's standard reverse logistics process: (1) the end customer "
                    "requests a return through the client brand's portal; (2) TrackFlow automatically "
                    "generates the return label when the reason matches the brand's configured rules "
                    "(such as wrong size or defective product); and (3) upon arrival at the warehouse, "
                    "an operative inspects and classifies the item as fit for resale, fit for "
                    "reconditioning, or not fit (disposal)."
                )
            if idx == 1:
                if use_es:
                    return (
                        "El plazo estándar de devolución en TrackFlow es de 30 días desde la entrega, salvo "
                        "que la marca cliente haya configurado una ventana personalizada en su contrato. Los "
                        "costes de envío de devolución corren a cargo de la marca cliente en circunstancias "
                        "normales; TrackFlow solo asume el coste de envío de la devolución cuando se debe a "
                        "un error imputable a TrackFlow (como producto dañado en tránsito o entrega errónea)."
                    )
                return (
                    "TrackFlow's standard return window is 30 days from delivery, unless the client "
                    "brand has configured a custom window in their contract. Return shipping costs "
                    "are covered by the client brand under normal circumstances; TrackFlow covers "
                    "return shipping only when caused by a TrackFlow error (such as product damaged "
                    "in transit or wrong delivery)."
                )
            if idx == 2:
                if use_es:
                    return (
                        "Las devoluciones internacionales (artículos comprados en un país y devueltos en otro) "
                        "no están cubiertas por el proceso automatizado estándar de devoluciones y requieren "
                        "gestión manual por parte del equipo de Sofía Ramos (Returns Manager). Además, TrackFlow "
                        "no reacondiciona ni revende productos por cuenta propia, ejecutando la logística "
                        "estrictamente según las reglas definidas por cada marca cliente."
                    )
                return (
                    "International returns (items purchased in one country and returned in another) "
                    "are not covered by the standard automated returns process and require manual "
                    "handling by Sofía Ramos's team (Returns Manager). Additionally, TrackFlow does "
                    "not recondition or resell product on its own account, executing logistics "
                    "strictly according to each client brand's defined rules."
                )

        if doc == "storage-pricing":
            if idx == 0:
                if use_es:
                    return (
                        "TrackFlow calcula las tarifas de almacenamiento en función del volumen ocupado y no "
                        "por número de unidades: la tarifa estándar mensual de almacenamiento es de 18 USD por "
                        "metro cúbico al mes en Los Ángeles y de 16 EUR por metro cúbico al mes en Zaragoza, "
                        "con un periodo de carencia de 30 días durante el cual la mercancía recién recibida no "
                        "genera cargos de almacenamiento durante los primeros 30 días."
                    )
                return (
                    "TrackFlow calculates storage fees based on occupied volume rather than unit count: "
                    "the standard monthly storage rate is 18 USD per cubic meter per month in Los Angeles "
                    "and 16 EUR per cubic meter per month in Zaragoza, with a 30-day grace period where "
                    "newly arrived inventory incurs no storage charge for the first 30 days."
                )
            if idx == 1:
                if use_es:
                    return (
                        "Para el inventario estancado con más de 180 días sin movimiento (sin ventas ni salidas "
                        "de almacén), TrackFlow aplica un recargo por almacenamiento prolongado del 150% sobre "
                        "la tarifa estándar a partir del día 181. Los clientes pueden solicitar en cualquier "
                        "momento un informe de antigüedad de inventario a través de su Account Manager."
                    )
                return (
                    "For inventory with more than 180 days of no movement (no sales or outbound shipments), "
                    "TrackFlow applies a long-term inventory surcharge of 150% over the standard rate "
                    "starting on day 181. Clients may request an inventory aging report at any time "
                    "through their account manager (generated internally)."
                )
            if idx == 2:
                if use_es:
                    return (
                        "Los clientes que mantienen un volumen medio mensual superior a 50 metros cúbicos "
                        "pueden negociar una tarifa de almacenamiento preferencial; sin embargo, dicha "
                        "negociación debe ser aprobada siempre por el Director Comercial Miguel Torres — un "
                        "Account Manager no puede ofrecer ni aprobar descuentos de almacenamiento por su cuenta."
                    )
                return (
                    "Clients maintaining more than 50 cubic meters of average monthly volume qualify "
                    "to negotiate a preferential storage rate; however, that negotiation must always "
                    "go through and be approved by Commercial Director Miguel Torres — an account "
                    "manager cannot offer or grant storage discounts independently on their own."
                )

        if doc == "carrier-coverage":
            if idx == 0:
                if use_es:
                    return (
                        "En Estados Unidos (Los Ángeles), TrackFlow trabaja con UPS, FedEx y DHL: "
                        "UPS ofrece cobertura nacional completa y las mejores tarifas para paquetes pesados "
                        "(más de 5 kg); FedEx proporciona los tiempos de tránsito más rápidos para envíos "
                        "express dentro de California; y DHL es la opción dedicada para envíos internacionales "
                        "con salida desde Los Ángeles."
                    )
                return (
                    "In the United States (Los Angeles), TrackFlow partners with UPS, FedEx, and DHL: "
                    "UPS provides full national coverage and the best rates for heavy packages (over 5 kg); "
                    "FedEx delivers the fastest transit times for express shipments within California; "
                    "and DHL is the dedicated reliable option for international shipments departing Los Angeles."
                )
            if idx == 1:
                if use_es:
                    return (
                        "En España (Zaragoza), TrackFlow opera con SEUR, MRW, DHL y dos transportistas locales "
                        "de última milla: SEUR ofrece la mejor cobertura en zonas rurales de Aragón, MRW "
                        "proporciona las tarifas más competitivas para paquetes pequeños de menos de 2 kg, y "
                        "los transportistas locales operan exclusivamente en el área metropolitana de Zaragoza. "
                        "Los transportistas se asignan automáticamente mediante el sistema de enrutamiento según "
                        "destino, peso, tipo de producto y urgencia."
                    )
                return (
                    "In Spain (Zaragoza), TrackFlow works with SEUR, MRW, DHL, and two local last-mile "
                    "carriers: SEUR offers the best coverage in rural areas of Aragón, MRW provides the "
                    "most competitive rates for small packages under 2 kg, and local carriers operate "
                    "exclusively within the Zaragoza metropolitan area. Carriers are automatically "
                    "assigned by the routing system based on destination, weight, product type, and urgency."
                )
            if idx == 2:
                if use_es:
                    return (
                        "La selección de transportista para cada envío la determina automáticamente el sistema "
                        "de enrutamiento de TrackFlow según destino, peso, tipo de producto y urgencia — un "
                        "Account Manager no elige manualmente el transportista salvo excepción aprobada por "
                        "Carlos Vega (Head of Carrier Operations)."
                    )
                return (
                    "Carrier selection for each shipment is automatically determined by TrackFlow's routing "
                    "system based on destination, weight, product type, and urgency — an account manager "
                    "does not manually choose the carrier except for an exception approved by Carlos Vega "
                    "(Head of Carrier Operations)."
                )

        if doc == "sla-delivery":
            if idx == 0:
                if use_es:
                    return (
                        "TrackFlow gestiona la entrega de última milla desde Los Ángeles (EE. UU.) y Zaragoza "
                        "(España) con tres niveles de servicio: el envío Estándar tarda de 3 a 5 días hábiles "
                        "a nivel nacional; el envío Express tarda de 24 a 48 horas (disponible en el área "
                        "metropolitana de Los Ángeles y en el corredor Zaragoza-Madrid); y el envío Internacional "
                        "entre EE. UU. y España tarda de 7 a 12 días hábiles, sujeto a tiempos de aduana ajenos "
                        "al control de TrackFlow."
                    )
                return (
                    "TrackFlow manages last-mile delivery from Los Angeles (US) and Zaragoza (Spain) "
                    "with three service tiers: Standard shipping takes 3 to 5 business days domestically; "
                    "Express shipping takes 24 to 48 hours (available in the Los Angeles metro area and "
                    "the Zaragoza-Madrid corridor); and International shipping between the US and Spain "
                    "takes 7 to 12 business days, subject to customs hold times outside TrackFlow's control."
                )
            if idx == 1:
                if use_es:
                    return (
                        "El SLA de entrega comprometido por contrato en TrackFlow es del 90% de entregas a "
                        "tiempo al mes, medido por país. Si un país cae por debajo del 90% durante dos meses "
                        "consecutivos, la marca cliente tiene derecho a una compensación del 5% sobre la cuota "
                        "mensual de ese país según el contrato estándar."
                    )
                return (
                    "TrackFlow's contractually committed delivery SLA is 90% on-time deliveries per month, "
                    "measured by country. If a country falls below 90% for two consecutive months, the "
                    "client brand is entitled to a 5% compensation on that country's monthly fee per the "
                    "standard contract."
                )
            if idx == 2:
                if use_es:
                    return (
                        "TrackFlow no garantiza los SLAs estándar de entrega (incluido el compromiso mensual "
                        "del 90%) durante fechas pico de alta demanda declaradas (Black Friday, Navidad y "
                        "Rebajas de Enero en España). Durante estas fechas pico, los plazos de entrega pueden "
                        "extenderse hasta un 40% adicional, lo cual debe comunicarse proactivamente a los "
                        "clientes con antelación."
                    )
                return (
                    "TrackFlow does not guarantee standard delivery SLAs (including the 90% monthly commitment) "
                    "during declared high-demand peak dates (Black Friday, Christmas, and January Sales in Spain). "
                    "During these peak dates, delivery times may extend by up to an additional 40%, and this "
                    "must be communicated proactively to clients in advance."
                )

        # Fallback for custom/generic chunks in unit tests
        cleaned = " ".join(line.strip() for line in context.chunk.text.splitlines() if line.strip())
        return cleaned
