import os
from functools import lru_cache

STACK = os.getenv("STACK", "free")


@lru_cache(maxsize=1)
def _get_hf_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a batch of texts.
    Free tier: HuggingFace sentence-transformers (all-MiniLM-L6-v2, dim=384)
    Upgrade:   AWS Bedrock Titan Embeddings (dim=1536)
    """
    if not texts:
        return []
    if STACK == "bedrock":
        return _embed_bedrock(texts)
    return _embed_hf(texts)


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


def _embed_hf(texts: list[str]) -> list[list[float]]:
    model = _get_hf_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


def _embed_bedrock(texts: list[str]) -> list[list[float]]:
    import boto3, json
    client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    results = []
    for text in texts:
        body = json.dumps({"inputText": text})
        resp = client.invoke_model(
            modelId="amazon.titan-embed-text-v1",
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        results.append(json.loads(resp["body"].read())["embedding"])
    return results


def get_embedding_dim() -> int:
    """Return dimension for the active embedding model."""
    return 1536 if STACK == "bedrock" else 384
