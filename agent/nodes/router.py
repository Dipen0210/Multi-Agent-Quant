import time
from langchain_core.messages import AIMessage
from agent.state import AgentState


def router_node(state: AgentState) -> dict:
    """
    Kicks off the graph. Records start time and emits an SSE log message.
    All 3 analysis agents always run — routing logic can be extended here.
    """
    return {
        "start_time_ms": int(time.time() * 1000),
        "sources":       [],
        "messages": [AIMessage(content=f"Planning analysis for {state['ticker']}...")],
    }
