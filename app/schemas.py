from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str = Field(description="Line item description as printed")
    quantity: float | None = Field(default=None, description="Quantity; null if absent")
    unit_price: float | None = Field(default=None, description="Per-unit price")
    amount: float = Field(description="Line total")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Model's certainty this line was read correctly",
    )


class InvoiceSchema(BaseModel):
    vendor: str = Field(description="Vendor / merchant name")
    vendor_confidence: float = Field(ge=0.0, le=1.0)
    invoice_number: str | None = None
    invoice_number_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    date: str | None = Field(
        default=None, description="ISO 8601 date if determinable"
    )
    date_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    currency: str = Field(description="ISO 4217 code, e.g. USD, INR, EUR")
    currency_confidence: float = Field(ge=0.0, le=1.0)
    subtotal: float | None = None
    subtotal_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    tax: float | None = None
    tax_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    total: float = Field(description="Grand total")
    total_confidence: float = Field(ge=0.0, le=1.0)
    line_items: list[LineItem]
    overall_confidence: float = Field(ge=0.0, le=1.0)


class IngestResponse(BaseModel):
    doc_id: str
    status: str  # "auto_approved" | "pending_review" | "blocked"
    extracted: InvoiceSchema | None
    flagged_fields: list[str]
    cost_usd: float
    provider: str
    model: str


class ReviewItemOut(BaseModel):
    doc_id: str
    field_name: str
    extracted_value: str | None
    confidence: float
    image_url: str


class ApproveRequest(BaseModel):
    doc_id: str
    corrections: dict[str, str]  # field_name -> corrected value


class DocumentOut(BaseModel):
    doc_id: str
    filename: str
    status: str
    provider: str
    model: str
    cost_usd: float
    created_at: str
    extracted: InvoiceSchema | None
    reviewed: dict | None
    image_url: str | None
    blocked_reason: str | None
