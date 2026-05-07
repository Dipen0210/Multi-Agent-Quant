import time
from datetime import datetime, timezone
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import AgentResponse


def formatter_node(state: AgentState) -> dict:
    """Assemble all agent outputs into the final AgentResponse."""
    elapsed = int(time.time() * 1000) - state.get("start_time_ms", 0)

    portfolio = state.get("portfolio_signal")
    signal     = portfolio.signal     if portfolio else "HOLD"
    confidence = portfolio.confidence if portfolio else 0.0

    response = AgentResponse(
        ticker=state["ticker"],
        signal=signal,
        confidence=confidence,
        news_analyst=state.get("news_analyst"),
        technical_analyst=state.get("technical_analyst"),
        macro_context=state.get("macro_context"),
        risk_manager=state.get("risk_decision"),
        portfolio_manager=portfolio,
        critic=state.get("critic_decision"),
        trade_executed=state.get("trade_execution"),
        sources=list(set(state.get("sources", []))),
        analysis_time_ms=elapsed,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    return {
        "messages": [AIMessage(content=f"Done — {signal} @ confidence {confidence:.2f} ({elapsed}ms)")],
        # Store serialised response in messages for API layer to extract
        "messages": [AIMessage(content=response.model_dump_json())],
    }
