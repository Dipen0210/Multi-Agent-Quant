from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.tools.alpaca_tool import skip_trade


def execution_node(state: AgentState) -> dict:
    # Phase 7 — placeholder always skips
    return {
        "trade_execution": skip_trade("placeholder — Phase 7 not yet implemented"),
        "messages": [AIMessage(content="[Execution] placeholder — Phase 7")],
    }
