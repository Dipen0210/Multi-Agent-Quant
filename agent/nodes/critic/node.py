import os
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import CriticDecision

CONFIDENCE_THRESHOLD = float(os.getenv("CRITIC_CONFIDENCE_THRESHOLD", "0.60"))

DEBATE_PROMPT = """You are a final validator reviewing a trading recommendation.
The Portfolio Manager made a pure-sentiment decision.
The Risk Manager assessed market safety for today.
Your job: debate whether the sentiment signal is strong enough to act given market conditions.

Ticker: {ticker}
Portfolio Manager says: {signal} (confidence {confidence:.2f})
Bull case: {bull_case}
Bear case: {bear_case}

Risk Manager says: {rm_decision}
Market today: VIX={vix} ({risk_env}), SPY 5d={spy_5d}, DXY={dxy}
Safety flags: {flags}
Market safety scale used: {safety_scale}

Should we proceed with the trade? Consider:
- Is the sentiment signal strong enough to override any market risk flags?
- Does the PM confidence justify acting despite market conditions?
- Are there any critical concerns not already captured?

Reply ONLY with this JSON:
{{"veto": false, "flags": ["optional concern 1"], "reason": "one sentence"}}
Set veto=true only for serious new concerns not already captured by Risk Manager."""


def _count_source_agreement(state: AgentState, signal: str) -> tuple[int, int]:
    """
    Count how many sources agree with the signal direction.
    For BUY/SELL: counts bullish/bearish sources.
    For HOLD: counts whichever direction has the most sources (showing the dominant sentiment).
    """
    fn  = state.get("financial_news")
    rd  = state.get("reddit_sentiment")
    sec = state.get("sec_filing")
    ana = state.get("analyst_ratings")

    bullish = bearish = total = 0
    for src in [fn, rd, sec, ana]:
        if src is None:
            continue
        total += 1
        d = src.decision.lower()
        if d == "bullish": bullish += 1
        if d == "bearish": bearish += 1

    if signal == "BUY":
        return bullish, total
    if signal == "SELL":
        return bearish, total
    # HOLD: show whichever direction dominated so the user understands the underlying sentiment
    return max(bullish, bearish), total


def _llm_debate(state: AgentState) -> tuple[list[str], bool]:
    """Ask LLM to debate whether to proceed. Returns (extra_flags, should_veto)."""
    try:
        import json
        from agent.tools.llm_client import get_llm

        port  = state.get("portfolio_signal")
        risk  = state.get("risk_decision")
        macro = state.get("macro_context")

        prompt_text = DEBATE_PROMPT.format(
            ticker=state["ticker"],
            signal=port.signal     if port  else "HOLD",
            confidence=port.confidence if port else 0.0,
            bull_case=(port.bull_case[:120] if port else "N/A"),
            bear_case=(port.bear_case[:120] if port else "N/A"),
            rm_decision=risk.decision if risk else "N/A",
            vix=macro.vix           if macro else "N/A",
            risk_env=macro.risk_environment if macro else "N/A",
            spy_5d=f"{macro.spy_5d_return:.1%}" if macro else "N/A",
            dxy=macro.dxy           if macro else "N/A",
            flags=", ".join(risk.market_safety_flags) if risk and risk.market_safety_flags else "none",
            safety_scale=round(
                risk.adjusted_size / risk.original_size, 2
            ) if risk and risk.original_size > 0 else "N/A",
        )

        resp = get_llm().invoke(prompt_text)
        raw  = resp.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()

        data  = json.loads(raw)
        flags = data.get("flags", [])
        veto  = bool(data.get("veto", False))
        return flags, veto
    except Exception as e:
        return [f"LLM debate unavailable: {e}"], False


def critic_node(state: AgentState) -> dict:
    portfolio = state.get("portfolio_signal")
    risk      = state.get("risk_decision")

    signal     = portfolio.signal     if portfolio else "HOLD"
    confidence = portfolio.confidence if portfolio else 0.0
    flags: list[str] = []

    # Compute agreement first so it's always accurate in the response
    agree, total = _count_source_agreement(state, signal)
    agreement_str = f"{agree}/{total}"

    # ── Gate 1: Risk Manager veto passthrough ────────────────────────────────
    if risk and risk.decision == "VETOED":
        return _hold(f"Risk Manager veto: {risk.reason}", flags, agreement_str)

    # ── Gate 2: Confidence threshold ─────────────────────────────────────────
    if confidence < CONFIDENCE_THRESHOLD:
        flags.append(f"Confidence {confidence:.2f} below threshold {CONFIDENCE_THRESHOLD}")

    # ── Gate 3: Require 3/4 source agreement for BUY or SELL ─────────────────
    # With 4 sources, need at least 3. With 3 sources, need at least 2.
    min_agree = 3 if total >= 4 else (2 if total == 3 else total)
    if total > 0 and agree < min_agree:
        flags.append(f"Insufficient agreement: {agree}/{total} sources support {signal} (need {min_agree})")

    # ── Gate 4: Market safety flags from Risk Manager ─────────────────────────
    if risk and risk.market_safety_flags:
        flags.extend(risk.market_safety_flags)

    # ── Gate 5: LLM debate (advisory only — adds flags, cannot hard-veto) ─────
    if os.getenv("GROQ_API_KEY") or os.getenv("AWS_ACCESS_KEY_ID"):
        llm_flags, _ = _llm_debate(state)
        flags.extend(llm_flags)

    # ── Final decision ────────────────────────────────────────────────────────
    confidence_ok = confidence >= CONFIDENCE_THRESHOLD
    agreement_ok  = total == 0 or agree >= min_agree
    # Both gates must pass — low confidence alone or low agreement alone is not enough
    critical = not confidence_ok and not agreement_ok

    if critical or signal == "HOLD":
        reason = (
            f"Confidence {confidence:.2f} < {CONFIDENCE_THRESHOLD} and agreement {agreement_str} too low"
            if critical else
            f"Portfolio Manager signal is HOLD"
        )
        return _hold(reason, flags, agreement_str)

    return _proceed(flags, agreement_str, confidence)


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
            content=f"[Critic] ✓ PROCEED | agreement={agreement} | confidence={confidence:.2f} | flags={len(flags)}"
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
