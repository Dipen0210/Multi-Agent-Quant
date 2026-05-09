import time
from datetime import datetime, timezone
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import AgentResponse


def formatter_node(state: AgentState) -> dict:
    elapsed   = int(time.time() * 1000) - state.get("start_time_ms", 0)
    portfolio = state.get("portfolio_signal")
    critic    = state.get("critic_decision")

    pm_signal  = portfolio.signal     if portfolio else "HOLD"
    confidence = portfolio.confidence if portfolio else 0.0

    # If critic blocked the trade, final signal is HOLD regardless of PM
    signal = pm_signal if (critic and critic.decision == "PROCEED") else "HOLD"

    response = AgentResponse(
        ticker           = state["ticker"],
        signal           = signal,
        confidence       = confidence,
        financial_news   = state.get("financial_news"),
        reddit           = state.get("reddit_sentiment"),
        sec_filing       = state.get("sec_filing"),
        analyst_ratings  = state.get("analyst_ratings"),
        macro_context    = state.get("macro_context"),
        portfolio_manager= portfolio,
        risk_manager     = state.get("risk_decision"),
        critic           = state.get("critic_decision"),
        trade_executed   = state.get("trade_execution"),
        sources          = list(set(state.get("sources", []))),
        analysis_time_ms = elapsed,
        timestamp        = datetime.now(timezone.utc).isoformat(),
    )

    return {
        "messages": [AIMessage(content=response.model_dump_json())],
    }
