from app.providers.json_mode import JsonModeProvider


class OpenRouterProvider(JsonModeProvider):
    name = "openrouter"

    BASE_URL = "https://openrouter.ai/api/v1"
