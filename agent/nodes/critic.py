import os
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import CriticDecision

CONFIDENCE_THRESHOLD = float(os.getenv("CRITIC_CONFIDENCE_THRESHOLD", "0.65"))
MIN_HEADLINES        = 3
HIGH_VIX_WARN        = 25.0

REFLECTION_PROMPT = """You are a risk-focused critic reviewing a trading recommendation.
Briefly assess if there are any concerns with this recommendation that would warrant NOT trading.
Reply with a JSON object: {{"flags": ["flag1", "flag2"], "veto": true/false, "reason": "one sentence"}}
Only set veto=true for serious concerns. Empty flags list is fine if recommendation looks solid.

Ticker: {ticker}
Signal: {signal} (confidence {confidence})
News sentiment: {sentiment_label} ({sentiment_score}) from {headline_count} headlines
Technicals: RSI={rsi}, MACD={macd}, regime={regime}
Macro: VIX={vix}, {risk_environment}
Bull case: {bull_case}
Bear case: {bear_case}"""


def _count_agreement(state: AgentState, signal: str) -> tuple[int, int]:
    """Return (agents_agree, total_agents) with the portfolio signal."""
    news  = state.get("news_analyst")
    tech  = state.get("technical_analyst")
    macro = state.get("macro_context")

    agree = 0
    total = 0

    if news:
        total += 1
        if signal == "BUY"  and news.sentiment_label == "positive": agree += 1
        if signal == "SELL" and news.sentiment_label == "negative": agree += 1
        if signal == "HOLD" and news.sentiment_label == "neutral":  agree += 1

    if tech:
        total += 1
        bullish = tech.macd_signal in ("bullish", "bullish_crossover")
        bearish = tech.macd_signal in ("bearish", "bearish_crossover")
        if signal == "BUY"  and bullish: agree += 1
        if signal == "SELL" and bearish: agree += 1
        if signal == "HOLD" and not (bullish or bearish): agree += 1

    if macro:
        total += 1
        if signal == "BUY"  and macro.risk_environment == "risk_on":  agree += 1
        if signal == "SELL" and macro.risk_environment == "risk_off": agree += 1
        if signal == "HOLD": agree += 1  # macro never blocks a HOLD

    return agree, total


def _llm_reflection(state: AgentState) -> tuple[list[str], bool]:
    """Ask LLM to flag any additional concerns. Returns (flags, should_veto)."""
    try:
        import json
        from agent.tools.llm_client import get_llm

        news  = state.get("news_analyst")
        tech  = state.get("technical_analyst")
        macro = state.get("macro_context")
        port  = state.get("portfolio_signal")

        prompt = REFLECTION_PROMPT.format(
            ticker=state["ticker"],
            signal=port.signal if port else "HOLD",
            confidence=port.confidence if port else 0,
            sentiment_label=news.sentiment_label if news else "N/A",
            sentiment_score=news.sentiment_score if news else 0,
            headline_count=news.headline_count if news else 0,
            rsi=tech.rsi if tech else "N/A",
            macd=tech.macd_signal if tech else "N/A",
            regime=tech.regime if tech else "N/A",
            vix=macro.vix if macro else "N/A",
            risk_environment=macro.risk_environment if macro else "N/A",
            bull_case=(port.bull_case[:100] if port else "N/A"),
            bear_case=(port.bear_case[:100] if port else "N/A"),
        )

        resp = get_llm().invoke(prompt)
        raw  = resp.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()

        data  = json.loads(raw)
        flags = data.get("flags", [])
        veto  = bool(data.get("veto", False))
        return flags, veto
    except Exception as e:
        return [f"LLM reflection unavailable: {e}"], False


def critic_node(state: AgentState) -> dict:
    portfolio = state.get("portfolio_signal")
    news      = state.get("news_analyst")
    macro     = state.get("macro_context")
    risk      = state.get("risk_decision")

    signal     = portfolio.signal     if portfolio else "HOLD"
    confidence = portfolio.confidence if portfolio else 0.0
    flags: list[str] = []

    # ── Gate 1: Risk Manager veto passthrough ────────────────────────────────
    if risk and risk.decision == "VETOED":
        return _hold(f"Risk Manager veto: {risk.reason}", flags, "0/3")

    # ── Gate 2: Confidence threshold ─────────────────────────────────────────
    confidence_ok = confidence >= CONFIDENCE_THRESHOLD

    # ── Gate 3: Agent agreement ───────────────────────────────────────────────
    agree, total = _count_agreement(state, signal)
    agreement_str = f"{agree}/{total}"

    if agree < 2:
        flags.append(f"Low agent agreement: only {agree}/{total} agents support {signal}")

    # ── Gate 4: Rule-based red flags ──────────────────────────────────────────
    if news and news.headline_count < MIN_HEADLINES:
        flags.append(f"Thin news coverage: only {news.headline_count} headlines")

    if macro and macro.vix > HIGH_VIX_WARN:
        flags.append(f"Elevated VIX={macro.vix} — increased market uncertainty")

    # ── Gate 5: Optional LLM reflection ──────────────────────────────────────
    llm_veto = False
    if os.getenv("GROQ_API_KEY") or os.getenv("AWS_ACCESS_KEY_ID"):
        llm_flags, llm_veto = _llm_reflection(state)
        flags.extend(llm_flags)

    # ── Final decision ────────────────────────────────────────────────────────
    critical = not confidence_ok or agree < 2 or llm_veto

    if critical or signal == "HOLD":
        reason = (
            f"Confidence {confidence:.2f} < {CONFIDENCE_THRESHOLD}"
            if not confidence_ok else
            (f"LLM critic flagged veto" if llm_veto else
             f"Agent agreement {agreement_str} below threshold")
        )
        return _hold(reason, flags, agreement_str)

    return _proceed(flags, agreement_str, confidence)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _proceed(flags: list[str], agreement: str, confidence: float) -> dict:
    decision = CriticDecision(
        decision="PROCEED",
        confidence_check=True,
        agent_agreement=agreement,
        flags=flags,
        veto_reason=None,
    )
    return {
        "critic_decision": decision,
        "messages": [AIMessage(
            content=f"[Critic] ✓ PROCEED | agreement={agreement} | "
                    f"confidence={confidence:.2f} | flags={len(flags)}"
        )],
    }


def _hold(reason: str, flags: list[str], agreement: str) -> dict:
    decision = CriticDecision(
        decision="HOLD",
        confidence_check=False,
        agent_agreement=agreement,
        flags=flags,
        veto_reason=reason,
    )
    return {
        "critic_decision": decision,
        "messages": [AIMessage(
            content=f"[Critic] ✗ HOLD | {reason[:90]}"
        )],
    }
