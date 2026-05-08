from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from agent.graph import graph
from agent.schemas import AgentResponse
from api.sse import build_initial_state
import json

router = APIRouter()


class AskRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10, example="NVDA")
    days:   int = Field(default=2, ge=1, le=7)


@router.post("/ask", response_model=AgentResponse, summary="Run full 6-agent analysis")
def ask(req: AskRequest):
    """
    Synchronous endpoint — runs the full agent graph and returns
    the complete AgentResponse JSON when all agents finish.
    Use GET /stream for real-time step-by-step output.
    """
    try:
        state  = build_initial_state(req.ticker, req.days)
        result = graph.invoke(state)

        # Final message from formatter contains the serialised AgentResponse
        messages = result.get("messages", [])
        if messages:
            last = messages[-1]
            content = last.content if hasattr(last, "content") else str(last)
            return AgentResponse(**json.loads(content))

        raise HTTPException(status_code=500, detail="Graph returned no output")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
