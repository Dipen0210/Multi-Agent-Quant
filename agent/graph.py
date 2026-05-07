from langgraph.graph import StateGraph, START, END
from agent.state import AgentState
from agent.nodes.router           import router_node
from agent.nodes.news_analyst     import news_analyst_node
from agent.nodes.technical_analyst import technical_analyst_node
from agent.nodes.macro_agent      import macro_agent_node
from agent.nodes.risk_manager     import risk_manager_node
from agent.nodes.portfolio_manager import portfolio_manager_node
from agent.nodes.critic           import critic_node
from agent.nodes.execution        import execution_node
from agent.nodes.formatter        import formatter_node


def build_graph():
    builder = StateGraph(AgentState)

    # Register nodes
    builder.add_node("router",             router_node)
    builder.add_node("news_analyst",       news_analyst_node)
    builder.add_node("technical_analyst",  technical_analyst_node)
    builder.add_node("macro_agent",        macro_agent_node)
    builder.add_node("risk_manager",       risk_manager_node)
    builder.add_node("portfolio_manager",  portfolio_manager_node)
    builder.add_node("critic",             critic_node)
    builder.add_node("execution",          execution_node)
    builder.add_node("formatter",          formatter_node)

    # ── Analysis tier (parallel fan-out) ──────────────────────────────
    builder.add_edge(START,               "router")
    builder.add_edge("router",            "news_analyst")
    builder.add_edge("router",            "technical_analyst")
    builder.add_edge("router",            "macro_agent")

    # ── Decision tier (fan-in → sequential) ───────────────────────────
    builder.add_edge("news_analyst",      "risk_manager")
    builder.add_edge("technical_analyst", "risk_manager")
    builder.add_edge("macro_agent",       "risk_manager")
    builder.add_edge("risk_manager",      "portfolio_manager")
    builder.add_edge("portfolio_manager", "critic")

    # ── Critic routes to execution or direct to formatter ─────────────
    builder.add_conditional_edges(
        "critic",
        _route_after_critic,
        {"execution": "execution", "formatter": "formatter"},
    )
    builder.add_edge("execution", "formatter")
    builder.add_edge("formatter", END)

    return builder.compile()


def _route_after_critic(state: AgentState) -> str:
    decision = state.get("critic_decision")
    if decision and decision.decision == "PROCEED":
        return "execution"
    return "formatter"


# Module-level compiled graph — import this in the API
graph = build_graph()
