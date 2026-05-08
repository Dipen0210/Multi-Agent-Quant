from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from api.sse import stream_graph

router = APIRouter()


@router.get("/stream", summary="Stream agent steps via Server-Sent Events")
async def stream(
    ticker: str = Query(..., min_length=1, max_length=10, example="NVDA"),
    days:   int = Query(default=2, ge=1, le=7),
):
    """
    SSE endpoint — streams each agent step as it completes.

    Connect with EventSource in the browser or curl:
      curl -N "http://localhost:8000/stream?ticker=NVDA"

    Event types:
      step   → { node, message }       one agent completed
      result → full AgentResponse JSON  graph finished
      error  → { message }             something went wrong
    """
    return StreamingResponse(
        stream_graph(ticker, days),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
