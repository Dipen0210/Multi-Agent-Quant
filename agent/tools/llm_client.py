import os
from functools import lru_cache


STACK = os.getenv("STACK", "free")


@lru_cache(maxsize=1)
def get_llm():
    """Returns the configured LLM. Swap STACK env var to switch providers."""
    if STACK == "bedrock":
        from langchain_aws import ChatBedrock
        return ChatBedrock(
            model_id=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
    from langchain_groq import ChatGroq
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.0,
    )


@lru_cache(maxsize=1)
def get_vision_llm():
    """Returns vision-capable LLM for chart analysis."""
    if STACK == "bedrock":
        from langchain_aws import ChatBedrock
        return ChatBedrock(
            model_id=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
    from langchain_groq import ChatGroq
    return ChatGroq(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.0,
    )
