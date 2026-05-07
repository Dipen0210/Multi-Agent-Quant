import io
import base64
import yfinance as yf
import mplfinance as mpf
import matplotlib
matplotlib.use("Agg")
from langchain_core.messages import HumanMessage
from agent.tools.llm_client import get_vision_llm

VISION_PROMPT = (
    "You are a technical analysis expert. Analyze this candlestick chart with RSI and MACD. "
    "In one short sentence, identify the most prominent chart pattern (e.g. ascending triangle, "
    "double bottom, head and shoulders, bull flag, support bounce, etc.). "
    "Reply with ONLY the pattern name and a brief explanation — no other text."
)


def generate_chart_bytes(ticker: str) -> bytes:
    """Generate a candlestick chart with RSI + MACD panels. Returns PNG bytes."""
    hist = yf.Ticker(ticker).history(period="6mo")
    hist.index = hist.index.tz_localize(None)

    # RSI
    delta   = hist["Close"].diff()
    gain    = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
    loss    = (-delta).clip(lower=0).ewm(com=13, min_periods=14).mean()
    rsi     = 100 - (100 / (1 + gain / loss.replace(0, float("nan"))))

    # MACD
    ema12   = hist["Close"].ewm(span=12, adjust=False).mean()
    ema26   = hist["Close"].ewm(span=26, adjust=False).mean()
    macd    = ema12 - ema26
    signal  = macd.ewm(span=9, adjust=False).mean()

    add_plots = [
        mpf.make_addplot(rsi,   panel=1, color="blue",   ylabel="RSI",  ylim=(0, 100)),
        mpf.make_addplot(macd,  panel=2, color="green",  ylabel="MACD"),
        mpf.make_addplot(signal,panel=2, color="red"),
    ]

    buf = io.BytesIO()
    mpf.plot(
        hist,
        type="candle",
        style="yahoo",
        title=f"{ticker} — 6 Month Chart",
        addplot=add_plots,
        volume=True,
        panel_ratios=(3, 1, 1),
        savefig=dict(fname=buf, dpi=100, bbox_inches="tight"),
    )
    buf.seek(0)
    return buf.read()


def analyze_chart(ticker: str) -> str:
    """
    Generate chart and send to vision LLM for pattern recognition.
    Returns a short pattern description string.
    """
    try:
        chart_bytes  = generate_chart_bytes(ticker)
        b64          = base64.standard_b64encode(chart_bytes).decode()
        image_url    = f"data:image/png;base64,{b64}"

        llm = get_vision_llm()
        msg = HumanMessage(content=[
            {"type": "text",      "text": VISION_PROMPT},
            {"type": "image_url", "image_url": {"url": image_url}},
        ])
        response = llm.invoke([msg])
        return response.content.strip()
    except Exception as e:
        return f"chart analysis unavailable: {e}"
