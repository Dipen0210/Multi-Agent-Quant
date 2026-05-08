import os
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.tools.yfinance_tool import get_technicals
from agent.tools.chart_tool import analyze_chart


def technical_analyst_node(state: AgentState) -> dict:
    ticker = state["ticker"]
    output = get_technicals(ticker)

    if os.getenv("GROQ_API_KEY") or os.getenv("AWS_ACCESS_KEY_ID"):
        output.chart_pattern = analyze_chart(ticker)
    else:
        output.chart_pattern = "chart analysis skipped (no LLM key)"

    return {
        "technical_analyst": output,
        "messages": [AIMessage(
            content=f"[Technical Analyst] RSI={output.rsi} | "
                    f"MACD={output.macd_signal} | "
                    f"Regime={output.regime} | "
                    f"Pattern: {output.chart_pattern}"
        )],
    }
