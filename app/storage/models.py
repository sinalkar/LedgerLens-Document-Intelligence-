from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase): ...


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(primary_key=True)  # uuid4
    filename: Mapped[str]
    status: Mapped[str]  # pending_review | auto_approved | approved | blocked
    extracted_json: Mapped[str]  # raw InvoiceSchema dump
    reviewed_json: Mapped[str | None] = mapped_column(default=None)
    provider: Mapped[str]
    model: Mapped[str]
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[float] = mapped_column(default=0.0)
    image_path: Mapped[str] = mapped_column(default="")
    blocked_reason: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class ReviewItem(Base):
    __tablename__ = "review_queue"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_id: Mapped[str]
    field_name: Mapped[str]
    extracted_value: Mapped[str | None] = mapped_column(default=None)
    confidence: Mapped[float] = mapped_column(default=0.0)
    status: Mapped[str] = mapped_column(default="pending")  # pending | corrected | approved
    corrected_value: Mapped[str | None] = mapped_column(default=None)
