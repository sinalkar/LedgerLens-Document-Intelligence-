from openai import OpenAI

from app.config import get_settings


class ModerationUnavailableError(Exception):
    """The moderation backend itself failed — fail closed in production."""


class ModerationVerdict:
    def __init__(self, allowed: bool, reason: str | None, top_score: float):
        self.allowed = allowed
        self.reason = reason
        self.top_score = top_score


def moderate_image(b64_data_uri: str) -> ModerationVerdict:
    s = get_settings()
    if s.moderation_backend == "off":  # blocked in prod by config validation
        return ModerationVerdict(True, None, 0.0)

    try:
        # Moderation is ALWAYS OpenAI — independent of LLM_PROVIDER, since
        # only OpenAI exposes an image moderation endpoint.
        client = OpenAI(api_key=s.openai_api_key)
        resp = client.moderations.create(
            model="omni-moderation-latest",
            input=[{"type": "image_url", "image_url": {"url": b64_data_uri}}],
        )
    except Exception as e:
        if s.environment == "production":
            raise ModerationUnavailableError(str(e)) from e
        return ModerationVerdict(True, None, 0.0)  # fail open in dev only

    result = resp.results[0]
    scores = result.category_scores.model_dump()
    top_cat, top_score = max(scores.items(), key=lambda kv: kv[1])
    if top_score > s.moderation_block_threshold:
        return ModerationVerdict(False, f"blocked: {top_cat}", top_score)
    return ModerationVerdict(True, None, top_score)
