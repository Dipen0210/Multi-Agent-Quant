from langgraph.graph import StateGraph, START, END
from agent.state import AgentState

from agent.nodes.router.node                  import router_node
from agent.nodes.financial_news_agent.node    import financial_news_node
from agent.nodes.reddit_agent.node            import reddit_node
from agent.nodes.sec_agent.node               import sec_node
from agent.nodes.analyst_ratings_agent.node   import analyst_ratings_node
from agent.nodes.sentiment_aggregator.node    import sentiment_aggregator_node
from agent.nodes.technical_analyst.node       import technical_analyst_node
from agent.nodes.macro_agent.node             import macro_agent_node
from agent.nodes.risk_manager.node            import risk_manager_node
from agent.nodes.portfolio_manager.node       import portfolio_manager_node
from agent.nodes.critic.node                  import critic_node
from agent.nodes.execution.node               import execution_node
from agent.nodes.formatter.node               import formatter_node


def build_graph():
    builder = StateGraph(AgentState)

    # ── Register all nodes ────────────────────────────────────────────────────
    builder.add_node("router",                router_node)
    builder.add_node("financial_news",        financial_news_node)
    builder.add_node("reddit",                reddit_node)
    builder.add_node("sec",                   sec_node)
    builder.add_node("analyst_ratings",       analyst_ratings_node)
    builder.add_node("sentiment_aggregator",  sentiment_aggregator_node)
    builder.add_node("technical_analyst",     technical_analyst_node)
    builder.add_node("macro_agent",           macro_agent_node)
    builder.add_node("risk_manager",          risk_manager_node)
    builder.add_node("portfolio_manager",     portfolio_manager_node)
    builder.add_node("critic",                critic_node)
    builder.add_node("execution",             execution_node)
    builder.add_node("formatter",             formatter_node)

    # ── Fan-out from router (all parallel) ────────────────────────────────────
    #
    #               ┌── financial_news ──┐
    #               ├── reddit           ├──→ sentiment_aggregator ──┐
    # router ───────├── sec              ┘                           │
    #               ├── analyst_ratings  ┘                           ├──→ risk_manager → ...
    #               ├── technical_analyst ─────────────────────────────┤
    #               └── macro_agent ────────────────────────────────────┘
    #
    builder.add_edge(START,                    "router")
    builder.add_edge("router",                 "financial_news")
    builder.add_edge("router",                 "reddit")
    builder.add_edge("router",                 "sec")
    builder.add_edge("router",                 "analyst_ratings")
    builder.add_edge("router",                 "technical_analyst")
    builder.add_edge("router",                 "macro_agent")

    # ── 4 news agents fan-in → sentiment aggregator ───────────────────────────
    builder.add_edge("financial_news",         "sentiment_aggregator")
    builder.add_edge("reddit",                 "sentiment_aggregator")
    builder.add_edge("sec",                    "sentiment_aggregator")
    builder.add_edge("analyst_ratings",        "sentiment_aggregator")

    # ── Fan-in to risk manager ────────────────────────────────────────────────
    builder.add_edge("sentiment_aggregator",   "risk_manager")
    builder.add_edge("technical_analyst",      "risk_manager")
    builder.add_edge("macro_agent",            "risk_manager")

    # ── Sequential decision tier ──────────────────────────────────────────────
    builder.add_edge("risk_manager",           "portfolio_manager")
    builder.add_edge("portfolio_manager",      "critic")

    builder.add_conditional_edges(
        "critic",
        _route_after_critic,
        {"execution": "execution", "formatter": "formatter"},
    )
    builder.add_edge("execution",              "formatter")
    builder.add_edge("formatter",              END)

    return builder.compile()


def _route_after_critic(state: AgentState) -> str:
    decision = state.get("critic_decision")
    if decision and decision.decision == "PROCEED":
        return "execution"
    return "formatter"


graph = build_graph()
