from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import PortfolioSignal


def portfolio_manager_node(state: AgentState) -> dict:
    # Phase 5 — placeholder
    return {
        "portfolio_signal": PortfolioSignal(
            signal="HOLD",
            confidence=0.0,
            bull_case="placeholder",
            bear_case="placeholder",
            resolution="placeholder — Phase 5 not yet implemented",
        ),
        "messages": [AIMessage(content="[Portfolio Manager] placeholder — Phase 5")],
    }
