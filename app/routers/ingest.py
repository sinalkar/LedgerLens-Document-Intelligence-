import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.metrics import (
    AUTO_APPROVALS,
    DOCS_PROCESSED,
    EXTRACTION_LATENCY,
    MODERATION_BLOCKS,
    MODERATION_LATENCY,
    REVIEW_QUEUE_DEPTH,
    TOKEN_COST,
)
from app.providers import get_provider
from app.providers.base import ExtractionFailedError, ExtractionResult
from app.schemas import IngestResponse, InvoiceSchema
from app.services.cost import cost_usd
from app.services.extraction import apply_arithmetic_checks, normalize_date
from app.services.moderation import ModerationUnavailableError, moderate_image
from app.services.preprocess import UploadValidationError, preprocess, validate_upload
from app.services.router import route_fields
from app.services.watermark import stamp
from app.storage.db import get_db
from app.storage.files import get_file_store
from app.storage.models import Document, ReviewItem

logger = logging.getLogger(__name__)

router = APIRouter()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _field_value(invoice: InvoiceSchema, field_name: str) -> str | None:
    if field_name.startswith("line_items["):
        idx = int(field_name[len("line_items[") : -1])
        li = invoice.line_items[idx]
        return f"{li.description} | qty={li.quantity} | amount={li.amount}"
    value = getattr(invoice, field_name, None)
    return None if value is None else str(value)


def _field_confidence(invoice: InvoiceSchema, field_name: str) -> float:
    if field_name.startswith("line_items["):
        idx = int(field_name[len("line_items[") : -1])
        return invoice.line_items[idx].confidence
    return getattr(invoice, f"{field_name}_confidence", 0.0)


def persist_blocked(db: Session, filename: str, reason: str | None) -> str:
    doc_id = str(uuid4())
    db.add(
        Document(
            id=doc_id,
            filename=filename,
            status="blocked",
            extracted_json="{}",
            provider=get_settings().llm_provider,
            model="",
            blocked_reason=reason,
        )
    )
    db.commit()
    return doc_id


def persist_document(
    db: Session,
    doc_id: str,
    filename: str,
    status: str,
    invoice: InvoiceSchema,
    result: ExtractionResult,
    image_path: str,
    usd: float,
) -> None:
    db.add(
        Document(
            id=doc_id,
            filename=filename,
            status=status,
            extracted_json=invoice.model_dump_json(),
            provider=result.provider,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cost_usd=usd,
            image_path=image_path,
        )
    )
    db.commit()


def persist_review_items(
    db: Session, doc_id: str, invoice: InvoiceSchema, flagged: list[str]
) -> None:
    for field_name in flagged:
        db.add(
            ReviewItem(
                doc_id=doc_id,
                field_name=field_name,
                extracted_value=_field_value(invoice, field_name),
                confidence=_field_confidence(invoice, field_name),
                status="pending",
            )
        )
    db.commit()
    REVIEW_QUEUE_DEPTH.set(
        db.query(ReviewItem).filter(ReviewItem.status == "pending").count()
    )


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    file: UploadFile,
    provider=Depends(get_provider),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    raw = await file.read()
    try:
        validate_upload(raw)
    except UploadValidationError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    data_uri, img = preprocess(raw, settings.max_image_dimension)

    try:
        with MODERATION_LATENCY.time():
            verdict = moderate_image(data_uri)  # 1. gate
    except ModerationUnavailableError:
        raise HTTPException(503, "Moderation backend unavailable — failing closed")

    if not verdict.allowed:
        MODERATION_BLOCKS.inc()
        DOCS_PROCESSED.labels(status="blocked").inc()
        persist_blocked(db, file.filename or "upload", verdict.reason)
        logger.warning("Upload blocked by moderation gate: %s", verdict.reason)
        raise HTTPException(422, {"blocked_reason": verdict.reason})

    try:
        with EXTRACTION_LATENCY.time():
            result = provider.extract_invoice(data_uri)  # 2. extract
    except ExtractionFailedError as e:
        raise HTTPException(502, f"Extraction failed: {e}")

    invoice = normalize_date(result.invoice)
    invoice = apply_arithmetic_checks(invoice)  # 3. sanity cross-check
    status, flagged = route_fields(  # 4. route
        invoice, settings.review_confidence_threshold
    )

    doc_id = str(uuid4())
    stamped = stamp(img, doc_id, now_iso())  # 5. watermark
    image_path = get_file_store().save(doc_id, stamped)

    usd = cost_usd(
        result.provider, result.model, result.prompt_tokens, result.completion_tokens
    )
    persist_document(db, doc_id, file.filename or "upload", status, invoice, result, image_path, usd)
    if flagged:
        persist_review_items(db, doc_id, invoice, flagged)

    TOKEN_COST.inc(usd)  # 6. metrics
    DOCS_PROCESSED.labels(status=status).inc()
    if status == "auto_approved":
        AUTO_APPROVALS.inc()

    logger.info(
        "Ingested %s via %s/%s: status=%s flagged=%d cost=$%.6f attempts=%d",
        doc_id, result.provider, result.model, status, len(flagged), usd, result.attempts,
    )

    return IngestResponse(
        doc_id=doc_id,
        status=status,
        extracted=invoice,
        flagged_fields=flagged,
        cost_usd=usd,
        provider=result.provider,
        model=result.model,
    )
