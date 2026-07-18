import base64
import io

from PIL import Image

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class UploadValidationError(ValueError):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def validate_upload(raw: bytes) -> None:
    """Reject bad uploads before any processing. Checks magic bytes,
    not filenames — extensions lie."""
    if len(raw) > MAX_UPLOAD_BYTES:
        raise UploadValidationError("File exceeds 10 MB limit", status_code=413)
    if not (raw.startswith(_JPEG_MAGIC) or raw.startswith(_PNG_MAGIC)):
        raise UploadValidationError(
            "Only JPEG and PNG uploads are accepted", status_code=415
        )


def preprocess(raw_bytes: bytes, max_dim: int) -> tuple[str, Image.Image]:
    img = Image.open(io.BytesIO(raw_bytes))
    img = img.convert("RGB")
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)  # cost control
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.standard_b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}", img
