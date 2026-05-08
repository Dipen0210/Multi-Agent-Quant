import json
import time
from typing import AsyncGenerator
from agent.state import AgentState


def build_initial_state(ticker: str, days: int = 2) -> AgentState:
    return {
        "ticker":            ticker.upper(),
        "days":              days,
        "messages":          [],
        "sources":           [],
        "news_analyst":      None,
        "technical_analyst": None,
        "macro_context":     None,
        "risk_decision":     None,
        "portfolio_signal":  None,
        "critic_decision":   None,
        "trade_execution":   None,
        "start_time_ms":     int(time.time() * 1000),
    }


def _sse(event: str, data: dict | str) -> str:
    """Format a single SSE message."""
    payload = data if isinstance(data, str) else json.dumps(data)
    return f"event: {event}\ndata: {payload}\n\n"


async def stream_graph(ticker: str, days: int = 2) -> AsyncGenerator[str, None]:
    """
    Async generator that streams SSE events as the LangGraph runs.

    Event types:
      step   — one agent completed (content = agent log message)
      result — final AgentResponse JSON
      error  — something went wrong
    """
    from agent.graph import graph
    import json as _json

    state = build_initial_state(ticker, days)

    try:
        async for chunk in graph.astream(state, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                messages = node_output.get("messages", [])
                for msg in messages:
                    content = msg.content if hasattr(msg, "content") else str(msg)

                    # Last message from formatter is the full JSON result
                    if node_name == "formatter":
                        try:
                            result_data = _json.loads(content)
                            yield _sse("result", result_data)
                        except Exception:
                            yield _sse("result", {"raw": content})
                    else:
                        yield _sse("step", {
                            "node":    node_name,
                            "message": content,
                        })

    except Exception as e:
        yield _sse("error", {"message": str(e)})
