import json
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.schemas import DocumentOut, InvoiceSchema
from app.storage.db import get_db
from app.storage.models import Document

router = APIRouter()


def _to_out(doc: Document) -> DocumentOut:
    extracted = None
    if doc.extracted_json and doc.extracted_json != "{}":
        extracted = InvoiceSchema.model_validate_json(doc.extracted_json)
    return DocumentOut(
        doc_id=doc.id,
        filename=doc.filename,
        status=doc.status,
        provider=doc.provider,
        model=doc.model,
        cost_usd=doc.cost_usd,
        created_at=doc.created_at.isoformat(),
        extracted=extracted,
        reviewed=json.loads(doc.reviewed_json) if doc.reviewed_json else None,
        image_url=f"/documents/{doc.id}/image" if doc.image_path else None,
        blocked_reason=doc.blocked_reason,
    )


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    limit: int = 50, offset: int = 0, db: Session = Depends(get_db)
):
    docs = (
        db.query(Document)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(min(limit, 200))
        .all()
    )
    return [_to_out(d) for d in docs]


@router.get("/documents/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, f"Unknown document {doc_id}")
    return _to_out(doc)


@router.get("/documents/{doc_id}/image")
def get_document_image(doc_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if doc is None or not doc.image_path:
        raise HTTPException(404, "No image for this document")
    if doc.image_path.startswith("gs://"):
        from app.storage.files import GCSFileStore

        from fastapi.responses import RedirectResponse

        return RedirectResponse(GCSFileStore().signed_url(doc.image_path))
    if not os.path.exists(doc.image_path):
        raise HTTPException(404, "Image file missing on disk")
    return FileResponse(doc.image_path, media_type="image/png")
