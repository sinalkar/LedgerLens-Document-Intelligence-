import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.metrics import REVIEW_QUEUE_DEPTH
from app.schemas import ApproveRequest, ReviewItemOut
from app.storage.db import get_db
from app.storage.models import Document, ReviewItem

router = APIRouter()

# Numeric top-level fields: corrections to these are coerced to float so
# the reviewed record stays type-consistent with the extraction.
_NUMERIC_FIELDS = {"subtotal", "tax", "total"}


@router.get("/review", response_model=list[ReviewItemOut])
def pending_reviews(db: Session = Depends(get_db)):
    items = (
        db.query(ReviewItem)
        .filter(ReviewItem.status == "pending")
        .order_by(ReviewItem.doc_id, ReviewItem.id)
        .all()
    )
    return [
        ReviewItemOut(
            doc_id=item.doc_id,
            field_name=item.field_name,
            extracted_value=item.extracted_value,
            confidence=item.confidence,
            image_url=f"/documents/{item.doc_id}/image",
        )
        for item in items
    ]


@router.post("/approve")
def approve(req: ApproveRequest, db: Session = Depends(get_db)):
    doc = db.get(Document, req.doc_id)
    if doc is None:
        raise HTTPException(404, f"Unknown document {req.doc_id}")

    reviewed = json.loads(doc.reviewed_json or doc.extracted_json)
    for field_name, value in req.corrections.items():
        if field_name in _NUMERIC_FIELDS:
            try:
                reviewed[field_name] = float(value)
            except ValueError:
                raise HTTPException(422, f"{field_name} must be numeric, got {value!r}")
        elif field_name.startswith("line_items["):
            # Line-item corrections are free-text; kept in a side map rather
            # than destructively rewriting the structured line item.
            reviewed.setdefault("field_corrections", {})[field_name] = value
        else:
            reviewed[field_name] = value
    doc.reviewed_json = json.dumps(reviewed)

    items = (
        db.query(ReviewItem)
        .filter(ReviewItem.doc_id == req.doc_id, ReviewItem.status == "pending")
        .all()
    )
    for item in items:
        if item.field_name in req.corrections:
            item.status = "corrected"
            item.corrected_value = req.corrections[item.field_name]
        else:
            item.status = "approved"

    db.flush()  # session is autoflush=False; the counts below must see the updates
    remaining = (
        db.query(ReviewItem)
        .filter(ReviewItem.doc_id == req.doc_id, ReviewItem.status == "pending")
        .count()
    )
    if remaining == 0:
        doc.status = "approved"
    db.commit()

    REVIEW_QUEUE_DEPTH.set(
        db.query(ReviewItem).filter(ReviewItem.status == "pending").count()
    )
    return {"doc_id": req.doc_id, "status": doc.status, "remaining_pending": remaining}
