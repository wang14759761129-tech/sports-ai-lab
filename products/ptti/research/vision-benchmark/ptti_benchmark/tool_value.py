"""Decision-card validation; utility scores are engineering judgments, never benchmark measurements."""
SEVERITIES = {"NONE", "LOW", "MEDIUM", "BOTTLENECK", "SOON_BOTTLENECK"}
DECISIONS = {"A_NOW", "B_BENCHMARK", "C_LATER", "D_RESEARCH_ONLY", "E_REJECT"}
BENEFITS = {"accuracy", "dev_efficiency", "UX", "stability", "maintainability", "extensibility"}
COSTS = {"learning", "integration", "migration", "performance", "complexity"}
RISKS = {"Windows", "CUDA", "Python", "dependencies", "license", "weights_license", "VRAM",
         "project_health", "API_stability", "commercial_use"}


def validate_tool_card(card: dict) -> None:
    required = {"name", "problem_solved", "current_problem_severity", "current_solution", "before",
                "after", "benefits", "cost", "risks", "decision", "radar", "evidence_status", "sources"}
    if not required <= set(card):
        raise ValueError("INCOMPLETE_TOOL_VALUE_CARD")
    if card["current_problem_severity"] not in SEVERITIES or card["decision"] not in DECISIONS:
        raise ValueError("INVALID_TOOL_DECISION")
    if card["radar"] not in {"ADOPT", "TRIAL", "ASSESS", "HOLD"}:
        raise ValueError("INVALID_RADAR_RING")
    for field, keys in (("benefits", BENEFITS), ("cost", COSTS)):
        if set(card[field]) != keys or any(not isinstance(v, (int, float)) or not 0 <= v <= 10
                                          for v in card[field].values()):
            raise ValueError("INVALID_TOOL_SCORE")
    if set(card["risks"]) != RISKS or not all(card["risks"].values()):
        raise ValueError("INCOMPLETE_RISK_DISCLOSURE")
