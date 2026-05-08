import time
from langchain_core.messages import AIMessage
from agent.state import AgentState


def router_node(state: AgentState) -> dict:
    return {
        "start_time_ms": int(time.time() * 1000),
        "sources":       [],
        "messages": [AIMessage(content=f"Planning analysis for {state['ticker']}...")],
    }
