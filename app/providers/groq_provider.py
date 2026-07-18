from app.providers.json_mode import JsonModeProvider


class GroqProvider(JsonModeProvider):
    name = "groq"

    BASE_URL = "https://api.groq.com/openai/v1"
