"""
Intervention Engine
====================
Decides the *level* of friction to introduce before a discretionary purchase.
Never emits shame/guilt language — copy templates live in the API layer /
prompt layer, this module only returns a level + machine-readable trigger tags,
so product/design can iterate on tone without touching the decision logic.
"""

from dataclasses import dataclass, field
from enum import IntEnum


class InterventionLevel(IntEnum):
    NONE = 0
    SIMPLE_INSIGHT = 1
    GENTLE_WARNING = 2
    BUDGET_WARNING = 3
    STRONG_WAIT_RECOMMENDATION = 4
    EMERGENCY_ALERT = 5


@dataclass
class InterventionInput:
    impulse_score: int              # 0-100, from impulse_score.evaluate()
    budget_impact_pct: float        # 0-100+, from safe_to_spend.evaluate_purchase()
    overspend_risk: str             # LOW | MEDIUM | HIGH, from safe_to_spend.calculate_safe_to_spend()
    remaining_budget: float


@dataclass
class InterventionDecision:
    level: InterventionLevel
    triggers: list[str] = field(default_factory=list)


def decide(inp: InterventionInput) -> InterventionDecision:
    triggers = []
    level = InterventionLevel.NONE

    if inp.remaining_budget <= 0:
        return InterventionDecision(
            level=InterventionLevel.EMERGENCY_ALERT,
            triggers=["remaining_budget_exhausted"],
        )

    if inp.overspend_risk == "HIGH":
        level = max(level, InterventionLevel.STRONG_WAIT_RECOMMENDATION)
        triggers.append("high_overspend_risk")

    if inp.budget_impact_pct >= 40:
        level = max(level, InterventionLevel.STRONG_WAIT_RECOMMENDATION)
        triggers.append("large_budget_impact")
    elif inp.budget_impact_pct >= 20:
        level = max(level, InterventionLevel.BUDGET_WARNING)
        triggers.append("moderate_budget_impact")

    if inp.impulse_score >= 65:
        level = max(level, InterventionLevel.GENTLE_WARNING)
        triggers.append("high_impulse_score")
    elif inp.impulse_score >= 35:
        level = max(level, max(level, InterventionLevel.SIMPLE_INSIGHT))
        triggers.append("moderate_impulse_score")

    if level == InterventionLevel.NONE and not triggers:
        triggers.append("no_risk_indicators")

    return InterventionDecision(level=InterventionLevel(int(level)), triggers=triggers)
