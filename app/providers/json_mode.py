import json

from openai import OpenAI
from pydantic import ValidationError

from app.providers.base import EXTRACTION_SYSTEM, ExtractionFailedError, ExtractionResult
from app.schemas import InvoiceSchema


class JsonModeProvider:
    """For providers without native Pydantic structured outputs.

    Strategy: JSON mode + schema-in-prompt + validate + bounded retry,
    feeding the validation error back into the conversation — models fix
    their own JSON well. Same schema guarantee at the boundary as the
    native OpenAI path, different enforcement mechanism.
    """

    name = "jsonmode"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float,
        max_retries: int = 2,
    ):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries

    def _schema_prompt(self) -> str:
        return (
            "Respond ONLY with a JSON object matching this JSON Schema. "
            "No markdown fences, no commentary.\n"
            + json.dumps(InvoiceSchema.model_json_schema())
        )

    def extract_invoice(self, image_data_uri: str) -> ExtractionResult:
        messages = [
            {
                "role": "system",
                "content": EXTRACTION_SYSTEM + "\n" + self._schema_prompt(),
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_data_uri}},
                    {"type": "text", "text": "Extract this document."},
                ],
            },
        ]
        total_pt = total_ct = 0
        last_err: ValidationError | None = None
        for attempt in range(1, self.max_retries + 2):
            resp = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=messages,
                response_format={"type": "json_object"},
            )
            total_pt += resp.usage.prompt_tokens
            total_ct += resp.usage.completion_tokens
            raw = resp.choices[0].message.content
            try:
                invoice = InvoiceSchema.model_validate_json(raw)
                return ExtractionResult(
                    invoice, total_pt, total_ct, self.model, self.name, attempt
                )
            except ValidationError as e:
                last_err = e
                messages.append({"role": "assistant", "content": raw})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"That JSON failed validation:\n{e}\n"
                            "Return corrected JSON only."
                        ),
                    }
                )
        raise ExtractionFailedError(
            f"Schema validation failed after {self.max_retries + 1} attempts: {last_err}"
        )

    def health_check(self) -> bool:
        try:
            self.client.models.list()
            return True
        except Exception:
            return False
