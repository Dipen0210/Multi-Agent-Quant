from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.tools.yfinance_tool import get_macro_data


def macro_agent_node(state: AgentState) -> dict:
    output = get_macro_data()

    return {
        "macro_context": output,
        "messages": [AIMessage(
            content=f"[Macro Agent] VIX={output.vix} | "
                    f"10yr={output.yield_10yr}% | "
                    f"{output.fed_stance} Fed | "
                    f"{output.risk_environment}"
        )],
    }
