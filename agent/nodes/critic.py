from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import CriticDecision


def critic_node(state: AgentState) -> dict:
    # Phase 6 — placeholder always proceeds
    return {
        "critic_decision": CriticDecision(
            decision="HOLD",
            confidence_check=False,
            agent_agreement="0/3",
            flags=["placeholder — Phase 6 not yet implemented"],
        ),
        "messages": [AIMessage(content="[Critic] placeholder — Phase 6")],
    }
