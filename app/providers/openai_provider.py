from openai import OpenAI

from app.providers.base import EXTRACTION_SYSTEM, ExtractionResult
from app.schemas import InvoiceSchema


class OpenAIProvider:
    """Native structured outputs: the response is parsed straight into
    InvoiceSchema by the OpenAI SDK — no manual JSON validation loop."""

    name = "openai"

    def __init__(self, api_key: str, model: str, temperature: float):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature

    def extract_invoice(self, image_data_uri: str) -> ExtractionResult:
        resp = self.client.beta.chat.completions.parse(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_data_uri}},
                        {"type": "text", "text": "Extract this document."},
                    ],
                },
            ],
            response_format=InvoiceSchema,
        )
        return ExtractionResult(
            invoice=resp.choices[0].message.parsed,
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
            model=self.model,
            provider=self.name,
            attempts=1,
        )

    def health_check(self) -> bool:
        try:
            self.client.models.retrieve(self.model)
            return True
        except Exception:
            return False
