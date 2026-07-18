from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.schemas import InvoiceSchema

EXTRACTION_SYSTEM = """You are an invoice/receipt extraction engine.
Extract all fields from the image. For EVERY field, set `confidence`
between 0.0 and 1.0 reflecting how certain you are of the value as
read from the image. If a value is absent or illegible, use null and
confidence 0.0. Never invent line items."""


class ExtractionFailedError(RuntimeError):
    """Raised when the provider could not produce a schema-valid extraction."""


@dataclass
class ExtractionResult:
    invoice: InvoiceSchema
    prompt_tokens: int
    completion_tokens: int
    model: str
    provider: str
    attempts: int


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def extract_invoice(self, image_data_uri: str) -> ExtractionResult: ...

    def health_check(self) -> bool: ...
