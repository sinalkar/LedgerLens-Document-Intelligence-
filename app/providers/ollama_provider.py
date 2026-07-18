from app.providers.json_mode import JsonModeProvider


class OllamaProvider(JsonModeProvider):
    name = "ollama"

    # base_url comes from OLLAMA_BASE_URL; the API key is a dummy value
    # because the OpenAI SDK requires one but Ollama ignores it.
