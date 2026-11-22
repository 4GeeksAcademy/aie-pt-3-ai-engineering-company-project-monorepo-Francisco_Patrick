"""RFP Response Generation & Department Drafting Pipeline (Part 2 of 3).

Provides modular compliance rules, multi-dimensional parallel evaluation
(readability, relevance, compliance), and the isolated generator-evaluator
feedback loop per active fulfillment department.
"""

from data.pipelines.rfp_response_generation.compliance_rules import (
    BRIEFING_COMPLIANCE_RULES,
    ComplianceRuleDefinition,
    evaluate_compliance_rules,
)
from data.pipelines.rfp_response_generation.evaluator import (
    DepartmentSectionEvaluator,
    evaluate_readability,
    evaluate_relevance,
)
from data.pipelines.rfp_response_generation.pipeline import (
    DEFAULT_MAX_ATTEMPTS,
    RFPResponseGenerationPipeline,
)

__all__ = [
    "BRIEFING_COMPLIANCE_RULES",
    "ComplianceRuleDefinition",
    "DEFAULT_MAX_ATTEMPTS",
    "DepartmentSectionEvaluator",
    "RFPResponseGenerationPipeline",
    "evaluate_compliance_rules",
    "evaluate_readability",
    "evaluate_relevance",
]
