from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import RiskDecision


def risk_manager_node(state: AgentState) -> dict:
    # Phase 5 — placeholder passes through
    return {
        "risk_decision": RiskDecision(
            decision="APPROVED",
            original_size=100,
            adjusted_size=100,
            stop_loss_pct=0.05,
            stop_loss_price=0.0,
            reason="placeholder — Phase 5 not yet implemented",
        ),
        "messages": [AIMessage(content="[Risk Manager] placeholder — Phase 5")],
    }
